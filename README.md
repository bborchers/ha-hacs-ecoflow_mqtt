# EcoFlow MQTT – HACS Integration

Diese Home-Assistant-Integration portiert den direkten EcoFlow-Cloud-MQTT-Zugriff aus [ioBroker.ecoflow-mqtt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt). Sie benötigt keine ioBroker-Installation.

## Installation

Repository in HACS als Custom Repository vom Typ **Integration** hinzufügen und anschließend `EcoFlow MQTT` installieren. Danach Home Assistant neu starten und die Integration über **Einstellungen → Geräte & Dienste** einrichten.

Benötigt werden die EcoFlow-MQTT-Zugangsdaten (User-ID, MQTT username/password und Client-ID) sowie die Seriennummern der Geräte. Protobuf-Geräte werden im Gerätefeld mit Typ angegeben, zum Beispiel `HW51...=pstream`, `SN...=river3` oder `SN...=delta3`. Die Zugangsdaten können über die im ioBroker-Projekt dokumentierten Verfahren ermittelt werden.

## Aktueller Umfang

Die Integration unterstützt die JSON-Telemetrie der Delta-/River-Gerätefamilien sowie den Protobuf-Envelope von PowerStream und Stream (`pstream`, `pstream600`, `pstream800`, `stream_ultra`, `stream_ac_pro`). Für Stream Ultra und Stream AC Pro werden Batterie-, PV-, Netz-, Last- und Socket-Werte sowie Lade-/Entladezeiten und Reservegrenzen dekodiert. AC-Relais, Backup-Reserve, Lade-/Entladegrenzen und Verbrauchsmessung können ebenfalls geschrieben werden.

Die Kommunikation ist eine inoffizielle EcoFlow-Cloud-Schnittstelle. Änderungen durch EcoFlow können die Funktion beeinträchtigen.

## Lizenzhinweis

Die Portierung steht unter MIT-Lizenz und enthält Konzepte und Gerätemappings aus dem oben verlinkten MIT-lizenzierten ioBroker-Projekt.
