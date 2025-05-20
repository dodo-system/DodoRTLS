#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>

HardwareSerial mySerial2(2);

#define RESET 16
#define IO_RXD2 18
#define IO_TXD2 17
#define I2C_SDA 39
#define I2C_SCL 38

Adafruit_SSD1306 display(128, 64, &Wire, -1);

// Configurações WiFi e do servidor
const char* ssid = "SSID_NETWORK";
const char* password = "PASSWORD";
const char* serverName = "http://YOUR_ENDPOINT:5000/endpoint"; 

// Conecta no WiFi
void setupWiFi() {
  Serial.print("Conectando ao WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Conectado! IP: ");
  Serial.println(WiFi.localIP());
}

// Envia o JSON para o servidor Flask via HTTP POST
void sendToServer(String json_payload) {
  if(WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName); // Inicializa a conexão com o servidor
    http.addHeader("Content-Type", "application/json"); // Define o cabeçalho

    int httpResponseCode = http.POST(json_payload); // Envia o POST com o JSON

    if(httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Resposta do servidor: " + response);
    } else {
      Serial.println("Erro no POST: " + String(httpResponseCode));
    }
    http.end(); // Finaliza a conexão
  } else {
    Serial.println("WiFi desconectado!");
  }
}

void logoshow(void) {
    display.clearDisplay();
    display.setTextSize(2);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println(F("Get Range"));
    display.setCursor(0, 20);
    display.println(F("JSON"));
    display.setCursor(0, 40);
    display.println(F("A0"));
    display.display();
    delay(2000);
}

String response = "";
String rec_head = "AT+RANGE";

void setup() {
    pinMode(RESET, OUTPUT);
    digitalWrite(RESET, HIGH);

    Serial.begin(115200);
    Serial.println(F("Hello! ESP32-S3 AT command V1.0 Test"));
    mySerial2.begin(115200, SERIAL_8N1, IO_RXD2, IO_TXD2);
    mySerial2.println("AT");

    Wire.begin(I2C_SDA, I2C_SCL);
    delay(1000);
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println(F("SSD1306 allocation failed"));
        for (;;);
    }
    display.clearDisplay();
    logoshow();

    setupWiFi(); // Conecta ao WiFi
}

void loop() {
    while (Serial.available() > 0) {
        mySerial2.write(Serial.read());
        yield();
    }
    while (mySerial2.available() > 0) {
        char c = mySerial2.read();
        if (c == '\r')
            continue;
        else if (c == '\n' || c == '\r') {
            if (response.indexOf(rec_head) != -1) {
                range_analy(response);
            } else {
                Serial.println(response);
            }
            response = "";
        } else {
            response += c;
        }
    }
}

// Função que analisa a string e monta o JSON
void range_analy(String data) {
    String id_str = data.substring(data.indexOf("tid:") + 4, data.indexOf(",mask:"));
    String range_str = data.substring(data.indexOf("range:"), data.indexOf(",rssi:"));
    String rssi_str = data.substring(data.indexOf("rssi:"));

    int range_list[8];
    double rssi_list[8];
    int count = 0;

    count = sscanf(range_str.c_str(), "range:(%d,%d,%d,%d,%d,%d,%d,%d)",
                   &range_list[0], &range_list[1], &range_list[2], &range_list[3],
                   &range_list[4], &range_list[5], &range_list[6], &range_list[7]);

    if (count != 8) {
        Serial.println("RANGE ANALY ERROR");
        Serial.println(count);
        return;
    }

    count = sscanf(rssi_str.c_str(), "rssi:(%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf)",
                   &rssi_list[0], &rssi_list[1], &rssi_list[2], &rssi_list[3],
                   &rssi_list[4], &rssi_list[5], &rssi_list[6], &rssi_list[7]);

    if (count != 8) {
        Serial.println("RSSI ANALY ERROR");
        Serial.println(count);
        return;
    }

    // Monta o JSON com os dados analisados
    String json_str = "";
    json_str = json_str + "{\"id\":" + id_str + ",";
    json_str = json_str + "\"range\":[";
    for (int i = 0; i < 8; i++) {
        json_str += String(range_list[i]);
        if (i != 7)
            json_str += ",";
        else
            json_str += "]}";
    }
    Serial.println(json_str);

    // Envia o JSON para o servidor Flask
    sendToServer(json_str);
}