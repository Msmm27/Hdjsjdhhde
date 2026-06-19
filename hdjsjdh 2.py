<?php
// ============================================
// БОТ ДЛЯ СТАТИСТИКИ TENDO
// Работает 24/7, проверяет сообщения каждые 5 секунд
// Без CRON, без webhook!
// ============================================

// Загружаем настройки из .env
$env = file_get_contents(__DIR__ . '/.env');
$config = [];
foreach (explode("\n", $env) as $line) {
    $line = trim($line);
    if (empty($line) || strpos($line, '#') === 0) continue;
    list($key, $value) = explode('=', $line, 2);
    $config[trim($key)] = trim($value);
}

$botToken = $config['BOT_TOKEN'] ?? '';
$chatIds = explode(',', $config['CHAT_IDS'] ?? '');
$logFile = $config['LOG_FILE'] ?? 'visits.log';
$offsetFile = 'offset.txt';
$allowedIds = $chatIds;

if (empty($botToken)) die('Ошибка: нет токена в .env');

// Бесконечный цикл
while (true) {
    $lastOffset = file_exists($offsetFile) ? (int)file_get_contents($offsetFile) : 0;
    $updates = getUpdates($lastOffset);
    
    foreach ($updates as $update) {
        $chatId = $update['message']['chat']['id'] ?? null;
        $text = $update['message']['text'] ?? '';
        $updateId = $update['update_id'] ?? 0;
        
        if (!in_array($chatId, $allowedIds)) {
            sendTelegram($chatId, "⛔ Нет доступа.");
            continue;
        }
        
        if ($text === '/start') sendMenu($chatId);
        elseif ($text === '📊 За день' || $text === '/day') sendDailyStats($chatId);
        elseif ($text === '📈 За час' || $text === '/hour') sendHourlyStats($chatId);
        elseif ($text === '📅 За месяц' || $text === '/month') sendMonthlyStats($chatId);
        elseif ($text === '📊 Вся статистика' || $text === '/total') sendTotalStats($chatId);
        else sendMenu($chatId);
        
        if ($updateId > $lastOffset) {
            file_put_contents($offsetFile, $updateId + 1);
        }
    }
    
    // Ждём 5 секунд перед новой проверкой
    sleep(5);
}

// ============================================
// ФУНКЦИИ
// ============================================

function getUpdates($offset = 0) {
    global $botToken;
    $url = "https://api.telegram.org/bot{$botToken}/getUpdates?timeout=10&offset=" . ($offset + 1);
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    $response = curl_exec($ch);
    curl_close($ch);
    $data = json_decode($response, true);
    return $data['result'] ?? [];
}

function sendMenu($chatId) {
    $text = "🤖 <b>Статистика TENDO</b>\n\nВыберите отчёт:";
    $keyboard = [
        'inline_keyboard' => [
            [['text' => '📊 За день', 'callback_data' => 'daily'], ['text' => '📈 За час', 'callback_data' => 'hourly']],
            [['text' => '📅 За месяц', 'callback_data' => 'monthly'], ['text' => '📊 Вся статистика', 'callback_data' => 'total']]
        ]
    ];
    sendTelegram($chatId, $text, $keyboard);
}

function sendDailyStats($chatId) {
    global $logFile;
    if (!file_exists($logFile)) { sendTelegram($chatId, "📊 За день: 0"); return; }
    $visits = file($logFile, FILE_IGNORE_NEW_LINES);
    $today = date('Y-m-d');
    $count = 0; $unique = [];
    foreach ($visits as $line) {
        $data = json_decode($line, true);
        if ($data && strpos($data['time'], $today) === 0) {
            $count++;
            $unique[$data['userAgent']] = true;
        }
    }
    sendTelegram($chatId, "📊 <b>ЗА ДЕНЬ</b>\n📅 " . date('d.m.Y') . "\n━━━━━━━━━━━━\n👥 $count\n👤 " . count($unique));
}

function sendHourlyStats($chatId) {
    global $logFile;
    if (!file_exists($logFile)) { sendTelegram($chatId, "📈 За час: 0"); return; }
    $visits = file($logFile, FILE_IGNORE_NEW_LINES);
    $oneHourAgo = time() - 3600;
    $count = 0;
    foreach ($visits as $line) {
        $data = json_decode($line, true);
        if ($data && strtotime($data['time']) >= $oneHourAgo) $count++;
    }
    sendTelegram($chatId, "📈 <b>ЗА ЧАС</b>\n🕒 " . date('H:i') . "\n━━━━━━━━━━━━\n👥 $count");
}

function sendMonthlyStats($chatId) {
    global $logFile;
    if (!file_exists($logFile)) { sendTelegram($chatId, "📅 За месяц: 0"); return; }
    $visits = file($logFile, FILE_IGNORE_NEW_LINES);
    $monthStart = date('Y-m-01');
    $count = 0; $unique = [];
    foreach ($visits as $line) {
        $data = json_decode($line, true);
        if ($data && strpos($data['time'], $monthStart) === 0) {
            $count++;
            $unique[$data['userAgent']] = true;
        }
    }
    $days = date('j');
    $avg = $days > 0 ? round($count / $days) : 0;
    sendTelegram($chatId, "📅 <b>ЗА МЕСЯЦ</b>\n📆 " . date('F Y') . "\n━━━━━━━━━━━━\n👥 $count\n👤 " . count($unique) . "\n🔄 $avg/день");
}

function sendTotalStats($chatId) {
    global $logFile;
    if (!file_exists($logFile)) { sendTelegram($chatId, "📊 Всего: 0"); return; }
    $visits = file($logFile, FILE_IGNORE_NEW_LINES);
    $total = count($visits);
    $unique = [];
    $first = null;
    foreach ($visits as $line) {
        $data = json_decode($line, true);
        if ($data) {
            if (!$first) $first = $data['time'];
            $unique[$data['userAgent']] = true;
        }
    }
    sendTelegram($chatId, "📊 <b>ВСЯ СТАТИСТИКА</b>\n━━━━━━━━━━━━\n👥 $total\n👤 " . count($unique) . "\n🕐 " . ($first ? date('d.m.Y H:i', strtotime($first)) : '—'));
}

function sendTelegram($chatId, $text, $keyboard = null) {
    global $botToken;
    $url = "https://api.telegram.org/bot{$botToken}/sendMessage";
    $data = ['chat_id' => $chatId, 'text' => $text, 'parse_mode' => 'HTML'];
    if ($keyboard) $data['reply_markup'] = json_encode($keyboard);
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_exec($ch);
    curl_close($ch);
}
?>