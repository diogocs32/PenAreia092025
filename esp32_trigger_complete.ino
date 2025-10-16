/*
 * PenAreia ESP32-C6 Trigger com Portal Captivo
 *
 * Funcionalidades:
 * - Portal captivo para configuração WiFi inicial
 * - Descoberta automática do servidor PenAreia via mDNS
 * - Reset de configurações (botão pressionado por 10s)
 * - Estados do LED: rápido=sem WiFi, 3x lento=conectado, fixo=pronto, apagado=cooldown
 * - Cooldown de 20 segundos entre triggers
 *
 * Hardware:
 * - ESP32-C6
 * - Botão no GPIO 9 (pull-up interno)
 * - LED no GPIO 8
 *
 * Autor: Sistema PenAreia
 * Versão: 2.0
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>

// =============================================================================
// CONFIGURAÇÕES HARDWARE
// =============================================================================
const int BUTTON_PIN = 9;
const int LED_PIN = 8;

// =============================================================================
// CONFIGURAÇÕES SISTEMA
// =============================================================================
const char *AP_SSID = "PenAreia-Setup";
const char *AP_PASSWORD = "12345678";
const unsigned long BUTTON_DEBOUNCE = 50;
const unsigned long RESET_HOLD_TIME = 10000;       // 10 segundos para reset
const unsigned long TRIGGER_COOLDOWN = 20000;      // 20 segundos cooldown
const unsigned long WIFI_TIMEOUT = 30000;          // 30 segundos timeout WiFi
const unsigned long SERVER_CHECK_INTERVAL = 30000; // 30s entre verificações

// =============================================================================
// ESTADOS DO SISTEMA
// =============================================================================
enum SystemState
{
    STATE_AP_MODE,     // Modo AP para configuração
    STATE_CONNECTING,  // Conectando ao WiFi
    STATE_DISCOVERING, // Descobrindo servidor
    STATE_READY,       // Pronto para trigger
    STATE_COOLDOWN,    // Em cooldown
    STATE_ERROR        // Erro
};

enum LedPattern
{
    LED_OFF,           // Apagado
    LED_FAST_BLINK,    // Piscando rápido
    LED_SLOW_BLINK_3X, // 3 piscadas lentas
    LED_ON,            // Ligado fixo
    LED_ERROR_PATTERN  // Padrão de erro
};

// =============================================================================
// VARIÁVEIS GLOBAIS
// =============================================================================
Preferences preferences;
WebServer server(80);
DNSServer dnsServer;

SystemState currentState = STATE_AP_MODE;
LedPattern currentLedPattern = LED_FAST_BLINK;

String ssid = "";
String password = "";
String serverIP = "";
int serverPort = 5000;
bool serverFound = false;

unsigned long lastButtonPress = 0;
unsigned long lastTrigger = 0;
unsigned long lastServerCheck = 0;
unsigned long buttonPressStart = 0;
unsigned long lastLedUpdate = 0;

bool buttonState = HIGH;
bool lastButtonState = HIGH;
bool buttonPressed = false;
bool ledState = false;
int blinkCount = 0;

// =============================================================================
// SETUP
// =============================================================================
void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("🎬 === PenAreia ESP32-C6 Trigger v2.0 ===");

    // Configura hardware
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    // Inicializa preferências
    preferences.begin("penareia", false);

    // Carrega configurações salvas
    loadSettings();

    // Verifica se tem configurações válidas
    if (ssid.length() > 0)
    {
        Serial.println("📋 Configurações encontradas, tentando conectar...");
        currentState = STATE_CONNECTING;
        currentLedPattern = LED_FAST_BLINK;
        connectToWiFi();
    }
    else
    {
        Serial.println("⚙️ Primeira configuração, iniciando modo AP...");
        startAPMode();
    }

    Serial.println("✅ Sistema iniciado!");
    Serial.println("🔘 Segure botão por 10s para resetar configurações");
}

// =============================================================================
// LOOP PRINCIPAL
// =============================================================================
void loop()
{
    handleButton();
    updateLED();

    switch (currentState)
    {
    case STATE_AP_MODE:
        dnsServer.processNextRequest();
        server.handleClient();
        break;

    case STATE_CONNECTING:
        checkWiFiConnection();
        break;

    case STATE_DISCOVERING:
        checkServerDiscovery();
        break;

    case STATE_READY:
        checkServerPeriodically();
        break;

    case STATE_COOLDOWN:
        checkCooldown();
        break;

    case STATE_ERROR:
        handleError();
        break;
    }

    delay(10);
}

// =============================================================================
// GERENCIAMENTO DE BOTÃO
// =============================================================================
void handleButton()
{
    int reading = digitalRead(BUTTON_PIN);
    unsigned long currentTime = millis();

    // Detecta mudança no botão
    if (reading != lastButtonState)
    {
        lastButtonPress = currentTime;

        if (reading == LOW)
        { // Botão pressionado
            buttonPressStart = currentTime;
            buttonPressed = true;
        }
        else
        { // Botão solto
            if (buttonPressed)
            {
                unsigned long pressDuration = currentTime - buttonPressStart;

                if (pressDuration >= RESET_HOLD_TIME)
                {
                    // Reset de configurações
                    handleReset();
                }
                else if (pressDuration > BUTTON_DEBOUNCE)
                {
                    // Trigger normal
                    handleTrigger();
                }

                buttonPressed = false;
            }
        }
    }

    // Verifica se ainda está pressionado para reset
    if (buttonPressed && (currentTime - buttonPressStart >= RESET_HOLD_TIME))
    {
        handleReset();
        buttonPressed = false;
    }

    lastButtonState = reading;
}

void handleReset()
{
    Serial.println("🔄 Reset de configurações iniciado...");

    // Pisca LED rapidamente durante reset
    for (int i = 0; i < 10; i++)
    {
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
        delay(100);
    }

    // Limpa configurações
    preferences.clear();
    ssid = "";
    password = "";
    serverIP = "";
    serverFound = false;

    Serial.println("✅ Configurações resetadas!");
    Serial.println("🔄 Reiniciando em modo AP...");

    // Reinicia em modo AP
    WiFi.disconnect();
    startAPMode();
}

void handleTrigger()
{
    unsigned long currentTime = millis();

    Serial.println("🔘 Botão pressionado!");

    // Verifica cooldown
    if (currentTime - lastTrigger < TRIGGER_COOLDOWN)
    {
        Serial.printf("⏳ Aguarde %lu segundos...\\n", (TRIGGER_COOLDOWN - (currentTime - lastTrigger)) / 1000);
        return;
    }

    // Verifica estado
    if (currentState != STATE_READY)
    {
        Serial.println("⚠️ Sistema não está pronto para trigger");
        return;
    }

    // Envia trigger
    lastTrigger = currentTime;
    sendTrigger();
}

// =============================================================================
// GERENCIAMENTO WiFi
// =============================================================================
void loadSettings()
{
    ssid = preferences.getString("ssid", "");
    password = preferences.getString("password", "");
    serverIP = preferences.getString("serverIP", "");
    serverPort = preferences.getInt("serverPort", 5000);

    if (ssid.length() > 0)
    {
        Serial.printf("📡 SSID salvo: %s\\n", ssid.c_str());
    }
}

void saveSettings()
{
    preferences.putString("ssid", ssid);
    preferences.putString("password", password);
    preferences.putString("serverIP", serverIP);
    preferences.putInt("serverPort", serverPort);

    Serial.println("💾 Configurações salvas!");
}

void startAPMode()
{
    currentState = STATE_AP_MODE;
    currentLedPattern = LED_FAST_BLINK;

    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);

    Serial.printf("📱 Modo AP iniciado: %s\\n", AP_SSID);
    Serial.printf("🔐 Senha: %s\\n", AP_PASSWORD);
    Serial.printf("🌐 IP: %s\\n", WiFi.softAPIP().toString().c_str());

    // Configura DNS captivo
    dnsServer.start(53, "*", WiFi.softAPIP());

    // Configura rotas do servidor web
    setupWebServer();
    server.begin();

    Serial.println("✅ Portal captivo ativo!");
    Serial.println("📱 Conecte-se à rede e acesse qualquer site");
}

void connectToWiFi()
{
    currentState = STATE_CONNECTING;
    currentLedPattern = LED_FAST_BLINK;

    Serial.printf("📶 Conectando ao WiFi: %s\\n", ssid.c_str());

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());

    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startTime) < WIFI_TIMEOUT)
    {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("✅ WiFi conectado!");
        Serial.printf("📍 IP: %s\\n", WiFi.localIP().toString().c_str());

        currentLedPattern = LED_SLOW_BLINK_3X;
        blinkCount = 0;

        // Aguarda 3 piscadas lentas completarem
        delay(2000);

        // Descobre servidor
        discoverServer();
    }
    else
    {
        Serial.println("❌ Falha na conexão WiFi!");
        Serial.println("🔄 Voltando para modo AP...");
        startAPMode();
    }
}

// =============================================================================
// DESCOBERTA DE SERVIDOR
// =============================================================================
void discoverServer()
{
    currentState = STATE_DISCOVERING;
    currentLedPattern = LED_FAST_BLINK;

    Serial.println("🔍 Descobrindo servidor PenAreia...");

    if (!MDNS.begin("esp32-trigger"))
    {
        Serial.println("❌ Erro ao inicializar mDNS");
        currentState = STATE_ERROR;
        return;
    }

    // Busca por serviços HTTP
    int n = MDNS.queryService("http", "tcp");

    if (n > 0)
    {
        Serial.printf("🔎 %d serviço(s) encontrado(s):\\n", n);

        for (int i = 0; i < n; i++)
        {
            String hostname = MDNS.hostname(i);
            IPAddress ip = MDNS.IP(i);
            int port = MDNS.port(i);

            Serial.printf("  %s: %s:%d\\n", hostname.c_str(), ip.toString().c_str(), port);

            // Verifica se é o servidor PenAreia
            if (testPenAreiaServer(ip.toString(), port))
            {
                serverIP = ip.toString();
                serverPort = port;
                serverFound = true;

                Serial.println("🎯 Servidor PenAreia encontrado!");
                Serial.printf("📡 %s:%d\\n", serverIP.c_str(), serverPort);

                saveSettings();

                currentState = STATE_READY;
                currentLedPattern = LED_ON;
                return;
            }
        }
    }

    Serial.println("⚠️ Servidor PenAreia não encontrado via mDNS");
    Serial.println("🔄 Tentando IP salvo...");

    // Tenta IP salvo
    if (serverIP.length() > 0 && testPenAreiaServer(serverIP, serverPort))
    {
        serverFound = true;
        currentState = STATE_READY;
        currentLedPattern = LED_ON;
        Serial.println("✅ Conectado ao servidor salvo!");
    }
    else
    {
        Serial.println("❌ Servidor não encontrado!");
        currentState = STATE_ERROR;
        currentLedPattern = LED_ERROR_PATTERN;
    }
}

bool testPenAreiaServer(String ip, int port)
{
    HTTPClient http;
    String url = "http://" + ip + ":" + String(port) + "/status";

    http.begin(url);
    http.setTimeout(5000);

    int httpCode = http.GET();
    bool isPenAreia = false;

    if (httpCode == HTTP_CODE_OK)
    {
        String payload = http.getString();

        // Verifica se é realmente o servidor PenAreia
        DynamicJsonDocument doc(1024);
        if (deserializeJson(doc, payload) == DeserializationError::Ok)
        {
            const char *status = doc["status"];
            if (status && strcmp(status, "online") == 0)
            {
                // Verifica se tem características do PenAreia
                if (doc.containsKey("video_source") && doc.containsKey("buffer_frames"))
                {
                    isPenAreia = true;
                }
            }
        }
    }

    http.end();
    return isPenAreia;
}

// =============================================================================
// GERENCIAMENTO DE ESTADOS
// =============================================================================
void checkWiFiConnection()
{
    if (WiFi.status() == WL_CONNECTED)
    {
        discoverServer();
    }
    else
    {
        // Timeout ou falha, volta para AP
        startAPMode();
    }
}

void checkServerDiscovery()
{
    // Estado transitório, não precisa fazer nada
    // A descoberta é iniciada por discoverServer()
}

void checkServerPeriodically()
{
    unsigned long currentTime = millis();

    if (currentTime - lastServerCheck > SERVER_CHECK_INTERVAL)
    {
        lastServerCheck = currentTime;

        if (!testPenAreiaServer(serverIP, serverPort))
        {
            Serial.println("⚠️ Servidor indisponível, redescobrir...");
            serverFound = false;
            discoverServer();
        }
    }
}

void checkCooldown()
{
    if (millis() - lastTrigger >= TRIGGER_COOLDOWN)
    {
        currentState = STATE_READY;
        currentLedPattern = LED_ON;
        Serial.println("✅ Cooldown finalizado, pronto para novo trigger");
    }
}

void handleError()
{
    // Tenta reconectar periodicamente
    static unsigned long lastRetry = 0;

    if (millis() - lastRetry > 30000)
    { // Retry a cada 30s
        lastRetry = millis();
        Serial.println("🔄 Tentando recuperar da falha...");

        if (WiFi.status() == WL_CONNECTED)
        {
            discoverServer();
        }
        else
        {
            connectToWiFi();
        }
    }
}

// =============================================================================
// ENVIO DE TRIGGER
// =============================================================================
void sendTrigger()
{
    if (!serverFound)
    {
        Serial.println("❌ Servidor não disponível!");
        return;
    }

    currentState = STATE_COOLDOWN;
    currentLedPattern = LED_OFF;

    HTTPClient http;
    String url = "http://" + serverIP + ":" + String(serverPort) + "/trigger";

    Serial.println("🎬 Enviando trigger...");

    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(30000);

    int httpCode = http.POST("{}");

    if (httpCode == HTTP_CODE_OK)
    {
        String response = http.getString();

        DynamicJsonDocument doc(2048);
        if (deserializeJson(doc, response) == DeserializationError::Ok)
        {
            bool success = doc["success"];
            const char *message = doc["message"];

            if (success)
            {
                Serial.println("✅ Trigger enviado com sucesso!");
                if (message)
                    Serial.printf("📄 %s\\n", message);

                // Pisca LED 3x para confirmar
                for (int i = 0; i < 3; i++)
                {
                    digitalWrite(LED_PIN, HIGH);
                    delay(200);
                    digitalWrite(LED_PIN, LOW);
                    delay(200);
                }
            }
            else
            {
                Serial.println("⚠️ Trigger enviado mas houve problemas");
                if (message)
                    Serial.printf("📄 %s\\n", message);
            }
        }
        else
        {
            Serial.println("✅ Trigger enviado (resposta não parseável)");
        }
    }
    else
    {
        Serial.printf("❌ Erro HTTP: %d\\n", httpCode);

        if (httpCode == -1)
        {
            Serial.println("🔍 Servidor pode ter mudado, redescobrir...");
            serverFound = false;
        }
    }

    http.end();
}

// =============================================================================
// GERENCIAMENTO DE LED
// =============================================================================
void updateLED()
{
    unsigned long currentTime = millis();

    switch (currentLedPattern)
    {
    case LED_OFF:
        digitalWrite(LED_PIN, LOW);
        break;

    case LED_ON:
        digitalWrite(LED_PIN, HIGH);
        break;

    case LED_FAST_BLINK:
        if (currentTime - lastLedUpdate > 200)
        { // 200ms
            ledState = !ledState;
            digitalWrite(LED_PIN, ledState);
            lastLedUpdate = currentTime;
        }
        break;

    case LED_SLOW_BLINK_3X:
        if (blinkCount < 6)
        { // 3 piscadas = 6 mudanças
            if (currentTime - lastLedUpdate > 500)
            { // 500ms
                ledState = !ledState;
                digitalWrite(LED_PIN, ledState);
                lastLedUpdate = currentTime;
                blinkCount++;
            }
        }
        else
        {
            // Terminou as 3 piscadas
            currentLedPattern = LED_ON;
            blinkCount = 0;
        }
        break;

    case LED_ERROR_PATTERN:
        // Padrão SOS: • • • — — — • • •
        // Implementar se necessário
        digitalWrite(LED_PIN, (currentTime / 100) % 2);
        break;
    }
}

// =============================================================================
// SERVIDOR WEB PARA CONFIGURAÇÃO
// =============================================================================
void setupWebServer()
{
    // Página principal
    server.on("/", handleRoot);
    server.on("/config", HTTP_POST, handleConfig);
    server.on("/status", handleStatus);

    // Captive portal - redireciona tudo para root
    server.onNotFound(handleRoot);
}

void handleRoot()
{
    String html = R"(
<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>PenAreia Setup</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f0f0f0; }
        .container { max-width: 400px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        input[type=text], input[type=password] { width: 100%; padding: 10px; margin: 5px 0 15px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        button:hover { background: #45a049; }
        .info { background: #e7f3ff; padding: 10px; border-left: 4px solid #2196F3; margin: 10px 0; }
        .status { text-align: center; margin: 10px 0; }
    </style>
</head>
<body>
    <div class='container'>
        <h1>🎬 PenAreia Setup</h1>
        
        <div class='info'>
            <strong>Status:</strong> Configuração necessária<br>
            <strong>IP:</strong> )" +
                  WiFi.softAPIP().toString() + R"(<br>
            <strong>Rede:</strong> )" +
                  AP_SSID + R"(
        </div>
        
        <form action='/config' method='POST'>
            <label>Rede WiFi:</label>
            <input type='text' name='ssid' placeholder='Nome da rede WiFi' required>
            
            <label>Senha WiFi:</label>
            <input type='password' name='password' placeholder='Senha da rede WiFi'>
            
            <button type='submit'>💾 Salvar e Conectar</button>
        </form>
        
        <div class='status'>
            <p><small>Após conectar, o sistema descobrirá automaticamente o servidor PenAreia na rede.</small></p>
        </div>
    </div>
</body>
</html>
  )";

    server.send(200, "text/html", html);
}

void handleConfig()
{
    String newSSID = server.arg("ssid");
    String newPassword = server.arg("password");

    if (newSSID.length() > 0)
    {
        ssid = newSSID;
        password = newPassword;

        String html = R"(
<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>PenAreia Setup</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f0f0f0; text-align: center; }
        .container { max-width: 400px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .success { background: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 15px 0; }
    </style>
    <script>
        setTimeout(function(){ window.close(); }, 5000);
    </script>
</head>
<body>
    <div class='container'>
        <h1>✅ Configuração Salva!</h1>
        <div class='success'>
            Conectando à rede: <strong>)" +
                      ssid + R"(</strong><br><br>
            O ESP32 tentará conectar e descobrir o servidor PenAreia automaticamente.<br><br>
            Esta janela fechará em 5 segundos.
        </div>
    </div>
</body>
</html>
    )";

        server.send(200, "text/html", html);

        // Salva e reconecta após resposta
        delay(2000);
        saveSettings();
        connectToWiFi();
    }
    else
    {
        server.send(400, "text/plain", "SSID é obrigatório!");
    }
}

void handleStatus()
{
    DynamicJsonDocument doc(512);

    doc["state"] = currentState;
    doc["wifi_connected"] = WiFi.status() == WL_CONNECTED;
    doc["server_found"] = serverFound;
    doc["server_ip"] = serverIP;
    doc["server_port"] = serverPort;
    doc["last_trigger"] = lastTrigger;
    doc["cooldown_remaining"] = max(0L, (long)(TRIGGER_COOLDOWN - (millis() - lastTrigger)));
    doc["uptime"] = millis();
    doc["free_heap"] = ESP.getFreeHeap();

    String response;
    serializeJson(doc, response);

    server.send(200, "application/json", response);
}