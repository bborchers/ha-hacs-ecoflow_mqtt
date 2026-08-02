# AGENTS.md – EcoFlow MQTT Home Assistant Integration

Dieses Dokument hält die technischen Erkenntnisse und Entscheidungen für die weitere Arbeit an diesem Repository fest. Es ist die Arbeitsgrundlage für menschliche und automatisierte Änderungen.

## Repository und Ziel

- Repository: `bborchers/ha-hacs-ecoflow_mqtt`
- Zweck: HACS-kompatible Home-Assistant-Integration für EcoFlow-Geräte über das inoffizielle Cloud-MQTT-Protokoll.
- Ursprungsprojekt und Protokollreferenz: [foxthefox/ioBroker.ecoflow-mqtt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt).
- Unterstützte Familien im aktuellen Stand: JSON-Geräte, PowerStream/Protobuf, Stream Ultra und Stream AC Pro.
- Die Integration kommuniziert direkt mit `mqtt-e.ecoflow.com` über TLS; ioBroker ist für die HACS-Integration nicht erforderlich.

## Arbeitsregeln

- Jede künftige technische Entscheidung und relevante Änderung muss in dieser `AGENTS.md` dokumentiert werden. Das gilt insbesondere für Architektur- und Protokollentscheidungen, neue Geräte oder Geräteprofile, Protobuf-Feldzuordnungen, Fehlerursachen und -korrekturen, Entitätsänderungen, Release-/Branch-Regeln sowie besondere Deployment- oder Betriebsmaßnahmen. Die Dokumentation ist im selben Pull Request wie die Änderung zu aktualisieren.
- Keine direkten Commits auf `main`. Änderungen erfolgen auf einem Feature-/Fix-Branch über Pull Request.
- `main` ist geschützt und kann nur über Pull Request geändert werden; ein zusätzliches Review ist nicht erforderlich. Force-Push ist deaktiviert.
- Commits verwenden Conventional Commits, zum Beispiel `fix(stream): decode nested load power list`.
- Vor jedem PR mindestens ausführen:

  ```bash
  python3 -m py_compile custom_components/ecoflow_mqtt/*.py
  git diff --check
  ```

- Bestehende Benutzeränderungen erhalten. Entitätsregistrierung und Home-Assistant-Konfiguration nicht ohne gezielte Sicherung verändern.
- Gerätebefehle zunächst mit konservativen Testwerten prüfen: falsche EcoFlow-Kommandos können Gerätefunktionen beeinflussen.

## Architektur

- `__init__.py` erstellt pro Config Entry einen `EcoFlowCoordinator` und lädt die Plattformen `sensor`, `switch` und `number`.
- `coordinator.py` verwaltet MQTT-Verbindung, Verfügbarkeit, Werte-Cache und Befehle.
- `protobuf.py` enthält einen kleinen Wire-Format-Codec und die Geräte-/Feldzuordnung.
- `const.py` enthält Sensor-, Switch- und Number-Definitionen einschließlich Einheit, Bereich und Schrittweite.
- Entitäten lesen ihren Wert über `coordinator.value(serial, key)` und erhalten Updates über `DataUpdateCoordinator`.
- Die Plattformen müssen Definitionen immer anhand von `coordinator.device_type(serial)` auswählen. Niemals alle JSON-, PowerStream- und Stream-Entitäten für jedes Gerät erzeugen; das produziert unpassende `unknown`-Entitäten.
- Der Config-Flow authentifiziert EcoFlow-Konten über `/auth/login` und `/iot-auth/app/certification`. User-ID, MQTT-Benutzer, MQTT-Passwort, Broker, Port und eine neue `ANDROID_<UUID>_<UserID>`-Client-ID werden zur Laufzeit ermittelt; das EcoFlow-Konto-Passwort wird nicht in der Config Entry gespeichert.
- Die API-Region ist im Config-Flow änderbar und wird standardmäßig auf `api-e.ecoflow.com` gesetzt. Die Zertifikats-URL wird für Paho von `mqtt://`/`mqtts://` bereinigt.
- Nach der Anmeldung wird `/device/list` mit Bearer-Token abgefragt. Gefundene Geräte können im Config-Flow ausgewählt werden und werden über `productName`/`deviceName` automatisch den Decoderfamilien `stream_ultra`, `stream_ac_pro`, `stream_ac`, `pstream` oder `json` zugeordnet. Wenn die private Geräteauflistung nicht verfügbar ist, bleibt eine manuelle `SERIAL=TYPE`-Eingabe als Fallback erhalten.
- Die automatische private Geräteauflistung ist bewusst fehlertolerant: EcoFlow-Konten, bei denen `/device/list` nicht erreichbar ist oder keine verwertbare Liste liefert, können mit den bereits ermittelten MQTT-Zugangsdaten über die manuelle Seriennummern-Eingabe eingerichtet werden. Das verhindert, dass eine erfolgreiche Anmeldung wegen einer regional oder kontoseitig nicht verfügbaren Liste verworfen wird.

## Gerätetypen und Entitäten

- `stream_*`: ausschließlich `STREAM_SENSORS`, `STREAM_SWITCHES` und `STREAM_NUMBERS`.
- `pstream*`: ausschließlich `PROTO_SENSORS`, `PROTO_SWITCHES` und `PROTO_NUMBERS`.
- Alle übrigen Geräte: JSON-Definitionen `SENSORS`, `SWITCHES` und `NUMBERS`.
- Stream AC Pro besitzt keine PV-Eingänge. Für `stream_ac_pro` werden `powGetPv`, `powGetPv2`, `powGetPv3`, `powGetPv4` und `powGetPvSum` nicht angelegt.
- Stream Ultra kann PV3/PV4 liefern; die Decoderfelder sind 996 (`powGetPv3`) und 997 (`powGetPv4`).
- Alte Entitäten können nach einer Plattformänderung im Entity Registry verbleiben. Erst prüfen, ob sie verwaist sind; gezielte Registry-Bereinigungen vorher sichern.

## Stream-Protobuf: wichtige Erkenntnisse

### Abfrage aktueller Werte

Stream Ultra/AC Pro verwenden nicht den PowerStream-Heartbeat-Request. Für `latestQuotas` muss ein Stream-Request mit den wesentlichen Headerfeldern `src=32`, `dest=32`, Zeitstempel und `from="ios"` gesendet werden. `encode_pstream_get()` darf für Stream-Geräte nicht verwendet werden.

### Empfang

- `DisplayPropertyUpload` ist `(cmdFunc=254, cmdId=21)`.
- `ConfigWrite` ist `(cmdFunc=254, cmdId=17)`.
- `day_resident_load_list` im Display-Telegramm ist Feld 978.
- Die Struktur ist doppelt verschachtelt:

  ```text
  DisplayPropertyUpload.978 day_resident_load_list
    -> field 1: repeated load / ResidentLoad
      -> field 1: start_min
      -> field 2: end_min
      -> field 3: load_power
  ```

- Deshalb darf `loadPower1` nicht direkt aus den Feldern 1/2/3 unter 978 gelesen werden.

### Schreiben

Für `ConfigWrite` gelten andere Feldnummern als im Display-Telegramm:

| Bedeutung | ConfigWrite-Feld |
|---|---:|
| `cmsMaxChgSoc` | 33 |
| `cmsMinDsgSoc` | 34 |
| `powConsumptionMeasurement` | 239 |
| `backupReverseSoc` | 102 |
| `feedGridModePowLimit` | 169 |
| `day_resident_load_list` | 379 |
| `relay2Onoff` | 380 |
| `relay3Onoff` | 381 |

Beim Schreiben von `cmsMaxChgSoc` und `cmsMinDsgSoc` müssen beide Werte gemeinsam übertragen werden. Der aktuelle Wert des jeweils anderen Limits kommt aus dem Coordinator-Cache.

`loadPower1` wird als `ConfigWrite.379 -> load field 1 -> ResidentLoad` geschrieben. Bekannte `startMin1`, `endMin1` und `feedGridModePowLimit` mit übertragen; keine künstlichen Nullwerte für unbekannte Werte erzeugen.

Der Slider `Base load power (partial automatic)` hat aktuell:

- Minimum: `0 W`
- Maximum: `1200 W`
- Schrittweite: `10 W`

`powConsumptionMeasurement` ist davon getrennt: Es ist die Betriebsart-Auswahl (`partial autom`/`smart meter`), nicht die einstellbare Grundlastleistung.

## Bekannte Home-Assistant-/MQTT-Themen

- Retained MQTT-Discovery-Nachrichten aus der alten ioBroker-Integration können weiterhin `homeassistant.components.mqtt`-Fehler erzeugen, etwa wegen `device_class: capacity`. Diese Fehler stammen nicht aus `custom_components/ecoflow_mqtt`.
- Bei Änderungen an Plattformdefinitionen können alte Entities weiter als `unknown` sichtbar sein. Die neuen gerätespezifischen Entities prüfen und verwaiste alte Entities anschließend gezielt löschen.
- Ein normaler `ha core restart` kann durch einen festhängenden Supervisor-Job blockiert sein. Vor einem Neustart `ha jobs info` prüfen. Falls erforderlich, Supervisor neu starten; ein direkter `docker restart homeassistant` ist nur als gezielte, autorisierte Diagnose-/Wartungsmaßnahme zu verwenden.
- Vor manuellen Änderungen an `/config/.storage/core.entity_registry` eine Kopie anlegen und nur explizit identifizierte Integrations-Entities bearbeiten.

## Release- und HACS-Regeln

- HACS verwendet die GitHub-Release-/Tag-Version. Ein Commit-Name darf nicht der einzige sichtbare Versionshinweis sein.
- `.github/workflows/release-drafter.yml` übernimmt den relevanten Release-Drafter-Workflow aus `ha-addons-grafana`; ha-addons-spezifische Deploy-/Dispatch-Schritte sind bewusst nicht enthalten.
- `.github/release-drafter.yml` löst die nächste Version aus PR-Labels `major`, `minor` und `patch`; Standard ist `patch`.
- Nach einem Merge nach `main` erzeugt Release Drafter den nächsten Release-Entwurf. Der erste veröffentlichte Release ist `v0.0.1`.
- Bei künftigen veröffentlichten Releases sollte zusätzlich die `version` in `custom_components/ecoflow_mqtt/manifest.json` mit dem Release-Tag synchronisiert werden.
- Nach einem Repository-Rename müssen README-Badges, HACS-URL, Issue-Tracker und Remote-URL geprüft werden.

## Verifikation und Debugging

1. Exakte betroffene Entity-ID und Gerätetyp feststellen.
2. Prüfen, ob die Entity zum passenden Definitionssatz gehört.
3. Coordinator-Cache und Decoderpfad prüfen: JSON versus `decode_pstream` versus `decode_stream`.
4. Bei Protobuf Änderungen mit kleinen lokalen Encode-/Decode-Tests prüfen; keine privaten MQTT-Nutzdaten ausgeben.
5. Nach dem Deployment Home-Assistant-Log auf `Error setting up entry`, `Error adding entity` und Decoderfehler prüfen.
6. Bei `unknown` zwischen „Gerät liefert das Feld nicht“ und „Entity ist für den falschen Gerätetyp angelegt“ unterscheiden.

## Referenzen

- [ioBroker EcoFlow MQTT](https://github.com/foxthefox/ioBroker.ecoflow-mqtt)
- [ha-addons-grafana](https://github.com/bborchers/ha-addons-grafana)
- [Conventional Commits](https://www.conventionalcommits.org/)
