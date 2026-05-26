<?php


function handle_pagos_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $subaction = $segments[2] ?? '';
    $pdo = get_db_connection();

    // POST /pagos/stripe/intent
    if ($method === 'POST' && $action === 'stripe' && $subaction === 'intent') {
        $user = get_authenticated_user();
        $pedido_id = $data['pedido_id'] ?? null;
        
        if (!$pedido_id) send_error_response("Falta pedido_id");

        $stmt = $pdo->prepare("SELECT total FROM Pedido WHERE id = ? AND usuario_id = ? AND estado = 'pendiente'");
        $stmt->execute([$pedido_id, $user['id']]);
        $pedido = $stmt->fetch();
        
        if (!$pedido) send_error_response("Pedido no válido o no encontrado", 404);

        $monto_centavos = intval($pedido['total'] * 100);
        
        if (empty(STRIPE_SECRET_KEY)) {
            // Simulador si no hay llave de Stripe (para dev/testing)
            $pdo->prepare("UPDATE Pedido SET stripe_payment_intent_id = 'pi_mock_dev' WHERE id = ?")->execute([$pedido_id]);
            send_json_response([
                "client_secret" => "pi_mock_dev_secret",
                "simulado" => true,
                "mensaje" => "Modo desarrollo activo. Claves Stripe no configuradas."
            ]);
        }

        // Llamada cURL a la API de Stripe
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, "https://api.stripe.com/v1/payment_intents");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
            'amount' => $monto_centavos,
            'currency' => 'mxn',
            'metadata' => ['pedido_id' => $pedido_id]
        ]));
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_USERPWD, STRIPE_SECRET_KEY . ":" . "");
        $result = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($http_code != 200) {
            error_log("Error Stripe: " . $result);
            send_error_response("Error al comunicar con pasarela de pagos", 500);
        }

        $stripe_res = json_decode($result, true);
        
        $pdo->prepare("UPDATE Pedido SET stripe_payment_intent_id = ? WHERE id = ?")
            ->execute([$stripe_res['id'], $pedido_id]);

        send_json_response(["client_secret" => $stripe_res['client_secret']]);
    }

    // POST /pagos/stripe/webhook
    if ($method === 'POST' && $action === 'stripe' && $subaction === 'webhook') {
        $payload = file_get_contents('php://input');
        $sig_header = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

        // Simplificado para recibir eventos (En PROD se debe verificar la firma con librerías nativas o ignorar si se está seguro del origen)
        $event = json_decode($payload, true);
        
        if ($event['type'] == 'payment_intent.succeeded') {
            $paymentIntent = $event['data']['object'];
            $pedido_id = $paymentIntent['metadata']['pedido_id'] ?? null;
            
            if ($pedido_id) {
                $pdo->prepare("UPDATE Pedido SET estado = 'confirmado' WHERE id = ? AND estado = 'pendiente'")
                    ->execute([$pedido_id]);
                    
                $pdo->prepare("INSERT INTO HistorialEstadoPedido (id, pedido_id, estado, notas) VALUES (?, ?, 'confirmado', 'Pago recibido vía Stripe')")
                    ->execute([generate_uuid(), $pedido_id]);
                    
                // Notificar admins
                $pdo->prepare("INSERT INTO Notificacion (id, usuario_id, tipo, mensaje, referencia_id, referencia_tipo) 
                               SELECT UUID(), id, 'general', CONCAT('Pago recibido para pedido #', SUBSTRING(?, 1, 8)), ?, 'pedido' 
                               FROM Usuario WHERE rol = 'admin'")
                    ->execute([$pedido_id, $pedido_id]);
            }
        }
        
        http_response_code(200);
        echo "OK";
        exit;
    }

    send_error_response("Ruta de pagos no encontrada", 404);
}
