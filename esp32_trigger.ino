/*
 * PenAreia ESP32-C6 Trigger Button
 *
 * Este código conecta o ESP32-C6 na rede WiFi e descobre automaticamente
 * o servidor PenAreia usando mDNS. Quando o botão é pressionado, envia
 * um trigger para gravar vídeo.
 *
 * Hardware necessário:
 * - ESP32-C6
 * - Botão push conectado ao GPIO 9 (com pull-up interno)
 * - LED opcional no GPIO 8 para indicação de status
 *
 * Bibliotecas necessárias:
 * - WiFi (incluída no core ESP32)
 * - ESPmDNS (incluída no core ESP32)
 * - HTTPClient (incluída no core ESP32)
 * - ArduinoJson (instalar via Library Manager)
 */

#include <WiFi.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// =============================================================================
// CONFIGURAÇÕES - EDITE AQUI
// =============================================================================

// Configurações WiFi
const char *ssid = "SUA_REDE_WIFI";      // Substitua pelo nome da sua rede
const char *password = "SUA_SENHA_WIFI"; // Substitua pela senha da sua rede

// Configurações do hardware
const int BUTTON_PIN = 9;  // GPIO do botão (com pull-up interno)
const int LED_PIN = 8;     // GPIO do LED de status
const int BUZZER_PIN = 10; // GPIO do buzzer (opcional)

// Configurações do serviço
const char *SERVICE_NAME = "PenAreia-Camera"; // Nome do serviço mDNS
const char *SERVICE_TYPE = "_http";           // Tipo do serviço
const char *SERVICE_PROTO = "_tcp";           // Protocolo

// Configurações de debounce
const unsigned long DEBOUNCE_DELAY = 50;     // ms
const unsigned long TRIGGER_COOLDOWN = 3000; // ms - evita múltiplos triggers

// =============================================================================
// VARIÁVEIS GLOBAIS
// =============================================================================

String serverIP = "";
int serverPort = 5000;
bool serverFound = false;
unsigned long lastButtonPress = 0;
unsigned long lastTrigger = 0;
bool buttonState = HIGH;
bool lastButtonState = HIGH;

// =============================================================================
// SETUP
// =============================================================================

void setup()
{
    Serial.begin(115200);
    Serial.println();
    Serial.println("🎬 === PenAreia ESP32-C6 Trigger ===");

    // Configura pinos
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    if (BUZZER_PIN > 0)
    {
        pinMode(BUZZER_PIN, OUTPUT);
    }

    // LED indica inicialização
    digitalWrite(LED_PIN, HIGH);

    // Conecta WiFi
    connectWiFi();

    // Descobre servidor PenAreia
    discoverServer();

    // LED indica pronto
    digitalWrite(LED_PIN, LOW);
    blinkLED(3, 200); // 3 piscadas rápidas = pronto

    Serial.println("✅ Sistema pronto!");
    Serial.println("🔘 Pressione o botão para disparar gravação");
}

// =============================================================================
// LOOP PRINCIPAL
// =============================================================================

void loop()
{
    // Verifica conexão WiFi
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("⚠️ WiFi desconectado, reconectando...");
        connectWiFi();
        return;
    }

    // Verifica servidor periodicamente
    static unsigned long lastServerCheck = 0;
    if (millis() - lastServerCheck > 30000)
    { // Verifica a cada 30s
        if (!serverFound)
        {
            Serial.println("🔍 Tentando descobrir servidor novamente...");
            discoverServer();
        }
        lastServerCheck = millis();
    }

    // Lê botão com debounce
    int reading = digitalRead(BUTTON_PIN);

    if (reading != lastButtonState)
    {
        lastButtonPress = millis();
    }

    if ((millis() - lastButtonPress) > DEBOUNCE_DELAY)
    {
        if (reading != buttonState)
        {
            buttonState = reading;

            // Botão pressionado (LOW = pressionado com pull-up)
            if (buttonState == LOW)
            {
                handleButtonPress();
            }
        }
    }

    lastButtonState = reading;

    delay(10); // Pequeno delay para estabilidade
}

// =============================================================================
// FUNÇÕES WiFi
// =============================================================================

void connectWiFi()
{
    Serial.print("📶 Conectando WiFi");
    WiFi.begin(ssid, password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20)
    {
        delay(500);
        Serial.print(".");
        attempts++;

        // Pisca LED durante conexão
        digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println();
        Serial.println("✅ WiFi conectado!");
        Serial.print("📍 IP: ");
        Serial.println(WiFi.localIP());
        digitalWrite(LED_PIN, LOW);
    }
    else
    {
        Serial.println();
        Serial.println("❌ Falha na conexão WiFi!");
        digitalWrite(LED_PIN, HIGH);
    }
}

// =============================================================================
// DESCOBERTA mDNS
// =============================================================================

void discoverServer()
{
    Serial.println("🔍 Descobrindo servidor PenAreia via mDNS...");

    if (!MDNS.begin("esp32-penareia-trigger"))
    {
        Serial.println("❌ Erro ao inicializar mDNS");
        return;
    }

    // Busca pelo serviço
    Serial.print("🔎 Buscando por ");
    Serial.print(SERVICE_NAME);
    Serial.println("...");

    int n = MDNS.queryService(SERVICE_TYPE, SERVICE_PROTO);

    if (n == 0)
    {
        Serial.println("⚠️ Nenhum serviço encontrado");
        serverFound = false;
    }
    else
    {
        Serial.printf("✅ %d serviço(s) encontrado(s):\\n", n);

        // Procura pelo serviço PenAreia
        for (int i = 0; i < n; ++i)
        {
            String instanceName = MDNS.hostname(i);
            Serial.printf("  %d: %s (%s:%d)\\n",
                          i + 1,
                          instanceName.c_str(),
                          MDNS.IP(i).toString().c_str(),
                          MDNS.port(i));

            // Verifica se é o nosso serviço
            if (instanceName.indexOf(SERVICE_NAME) >= 0)
            {
                serverIP = MDNS.IP(i).toString();
                serverPort = MDNS.port(i);
                serverFound = true;

                Serial.println("🎯 Servidor PenAreia encontrado!");
                Serial.printf("📡 Endereço: http://%s:%d\\n", serverIP.c_str(), serverPort);

                // Testa conexão
                if (testServerConnection())
                {
                    Serial.println("✅ Conexão com servidor confirmada!");
                    playSuccessSound();
                }
                break;
            }
        }

        if (!serverFound)
        {
            Serial.println("⚠️ Servidor PenAreia não encontrado nos serviços mDNS");
        }
    }
}

// =============================================================================
// COMUNICAÇÃO HTTP
// =============================================================================

bool testServerConnection()
{
    if (!serverFound)
        return false;

    HTTPClient http;
    String url = "http://" + serverIP + ":" + String(serverPort) + "/status";

    Serial.println("🧪 Testando conexão com servidor...");

    http.begin(url);
    http.setTimeout(5000);

    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK)
    {
        String payload = http.getString();

        // Parse JSON para verificar status
        DynamicJsonDocument doc(1024);
        DeserializationError error = deserializeJson(doc, payload);

        if (!error)
        {
            const char *status = doc["status"];
            if (status && strcmp(status, "online") == 0)
            {
                Serial.println("✅ Servidor online e funcionando!");
                http.end();
                return true;
            }
        }
    }

    Serial.printf("❌ Erro na conexão: %d\\n", httpCode);
    http.end();
    return false;
}

void sendTrigger()
{
    if (!serverFound)
    {
        Serial.println("❌ Servidor não encontrado! Tentando descobrir...");
        discoverServer();
        return;
    }

    HTTPClient http;
    String url = "http://" + serverIP + ":" + String(serverPort) + "/trigger";

    Serial.println("🎬 Enviando trigger para gravação...");

    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(30000); // 30s timeout para upload

    // Indica que está enviando
    digitalWrite(LED_PIN, HIGH);

    int httpCode = http.POST("{}");

    if (httpCode == HTTP_CODE_OK)
    {
        String response = http.getString();

        // Parse da resposta
        DynamicJsonDocument doc(2048);
        DeserializationError error = deserializeJson(doc, response);

        if (!error)
        {
            bool success = doc["success"];
            const char *message = doc["message"];
            const char *url = doc["url"];

            if (success)
            {
                Serial.println("✅ Gravação iniciada com sucesso!");
                if (message)
                    Serial.printf("📄 %s\\n", message);
                if (url)
                    Serial.printf("🔗 URL: %s\\n", url);

                playSuccessSound();
                blinkLED(5, 100); // 5 piscadas rápidas = sucesso
            }
            else
            {
                Serial.println("⚠️ Gravação iniciada mas houve problemas");
                if (message)
                    Serial.printf("📄 %s\\n", message);

                playWarningSound();
                blinkLED(3, 300); // 3 piscadas lentas = aviso
            }
        }
        else
        {
            Serial.println("✅ Trigger enviado (resposta não parseável)");
            blinkLED(2, 200);
        }
    }
    else
    {
        Serial.printf("❌ Erro HTTP: %d\\n", httpCode);

        if (httpCode == -1)
        {
            Serial.println("🔍 Servidor pode ter mudado, tentando redescobrir...");
            serverFound = false;
        }

        playErrorSound();
        blinkLED(10, 50); // Piscadas rápidas = erro
    }

    digitalWrite(LED_PIN, LOW);
    http.end();
}

// =============================================================================
// MANIPULAÇÃO DE EVENTOS
// =============================================================================

void handleButtonPress()
{
    unsigned long currentTime = millis();

    // Verifica cooldown
    if (currentTime - lastTrigger < TRIGGER_COOLDOWN)
    {
        Serial.println("⏳ Aguarde antes de pressionar novamente...");
        blinkLED(1, 100);
        return;
    }

    Serial.println("🔘 Botão pressionado!");
    lastTrigger = currentTime;

    // Verifica se está conectado
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("❌ WiFi desconectado!");
        playErrorSound();
        return;
    }

    // Envia trigger
    sendTrigger();
}

// =============================================================================
// FUNÇÕES DE FEEDBACK
// =============================================================================

void blinkLED(int times, int delayMs)
{
    for (int i = 0; i < times; i++)
    {
        digitalWrite(LED_PIN, HIGH);
        delay(delayMs);
        digitalWrite(LED_PIN, LOW);
        delay(delayMs);
    }
}

void playSuccessSound()
{
    if (BUZZER_PIN <= 0)
        return;

    // Dois beeps curtos
    tone(BUZZER_PIN, 1000, 100);
    delay(150);
    tone(BUZZER_PIN, 1200, 100);
}

void playWarningSound()
{
    if (BUZZER_PIN <= 0)
        return;

    // Três beeps médios
    for (int i = 0; i < 3; i++)
    {
        tone(BUZZER_PIN, 800, 200);
        delay(300);
    }
}

void playErrorSound()
{
    if (BUZZER_PIN <= 0)
        return;

    // Um beep longo grave
    tone(BUZZER_PIN, 400, 500);
}

// =============================================================================
// FUNÇÕES DE UTILIDADE
// =============================================================================

void printStatus()
{
    Serial.println("\\n📊 === STATUS DO SISTEMA ===");
    Serial.printf("📶 WiFi: %s\\n", WiFi.status() == WL_CONNECTED ? "Conectado" : "Desconectado");
    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.printf("📍 IP Local: %s\\n", WiFi.localIP().toString().c_str());
    }
    Serial.printf("🎯 Servidor: %s\\n", serverFound ? "Encontrado" : "Não encontrado");
    if (serverFound)
    {
        Serial.printf("📡 Endereço: http://%s:%d\\n", serverIP.c_str(), serverPort);
    }
    Serial.printf("🔘 Último trigger: %lu ms atrás\\n", millis() - lastTrigger);
    Serial.printf("💾 Memória livre: %d bytes\\n", ESP.getFreeHeap());
    Serial.println("================================\\n");
}