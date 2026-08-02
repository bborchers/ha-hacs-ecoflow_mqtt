# Home Assistant EcoFlow MQTT Integration

![project stage](https://img.shields.io/badge/project%20stage-experimental-yellow)
[![license](https://img.shields.io/github/license/bborchers/ha-hacs-ecoflow_mqtt)](LICENSE)
[![commit lint](https://github.com/bborchers/ha-hacs-ecoflow_mqtt/actions/workflows/commitlint.yml/badge.svg)](https://github.com/bborchers/ha-hacs-ecoflow_mqtt/actions/workflows/commitlint.yml)
![maintenance](https://img.shields.io/maintenance/yes/2026)
[![commit activity](https://img.shields.io/github/commit-activity/t/bborchers/ha-hacs-ecoflow_mqtt)](https://github.com/bborchers/ha-hacs-ecoflow_mqtt/commits/main)

Diese Integration befindet sich in einer frühen, experimentellen Phase. Es können sich Konfiguration, Entity-Namen und unterstützte Geräte zwischen Versionen ändern.

## Integration in diesem Repository

Die Integration verbindet Home Assistant direkt mit dem inoffiziellen EcoFlow-Cloud-MQTT-Dienst. Eine ioBroker-Installation ist nicht erforderlich.

| Bereich | Unterstützung |
|---|---|
| JSON-Geräte | Delta-/River-Gerätefamilien mit Kern-Telemetrie und Ausgängen |
| Protobuf-Geräte | PowerStream, Stream Ultra und Stream AC Pro |
| Sensoren | Batterie, PV, Netz, Last, Leistung, Spannung, Temperatur und Zeiten |
| Steuerung | AC/DC/Car-Ausgänge, Reservegrenzen, Stream-Relais und Verbrauchsmessung |
| Verbindung | TLS zu `mqtt-e.ecoflow.com` |

## Installation über HACS

1. Home Assistant → **HACS** → **Integrations**
2. Oben rechts (⋮) → **Custom repositories**
3. Repository-URL hinzufügen: `https://github.com/bborchers/ha-hacs-ecoflow_mqtt`
4. Kategorie **Integration** auswählen
5. `EcoFlow MQTT` installieren und Home Assistant neu starten
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen → EcoFlow MQTT** öffnen

## Konfiguration

Beim ersten Hinzufügen werden EcoFlow-Konto-E-Mail und -Passwort abgefragt. Die
Integration ermittelt damit User-ID, MQTT-Zugangsdaten, Broker, Port und Client-ID
direkt bei EcoFlow. Anschließend werden die Geräte des Kontos automatisch gefunden
und können ausgewählt werden. Das Konto-Passwort wird nicht in Home Assistant
gespeichert.

Für Europa ist `api-e.ecoflow.com` voreingestellt. Wenn EcoFlow für ein Konto
keine private Geräteliste liefert, erscheint ein manueller Fallback. Protobuf-Geräte
können dort mit Typ angegeben werden, zum Beispiel:

```text
HW51...=pstream
STREAM...=stream_ultra
STREAM...=stream_ac_pro
```

Mehrere Geräte werden kommasepariert eingetragen. Die Zugangsdaten können über die im [ioBroker-Referenzprojekt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt) beschriebenen Verfahren ermittelt werden.

## Sicherheit und Kompatibilität

Die Integration nutzt eine nicht-offizielle EcoFlow-Cloud-Schnittstelle. EcoFlow kann Protokoll, Zugangsdaten oder MQTT-Endpunkte jederzeit ändern. Schreibbefehle können die angeschlossenen Geräte beeinflussen; sie sollten zunächst mit konservativen Grenzwerten getestet werden.

## Entwicklung

Die lokale Integration liegt unter `custom_components/ecoflow_mqtt/`. Vor einem Commit sollten mindestens diese Prüfungen erfolgreich sein:

```bash
python3 -m py_compile custom_components/ecoflow_mqtt/*.py
git diff --check
```

## Commit-Regeln

Commits folgen [Conventional Commits](https://www.conventionalcommits.org/), analog zum zentralen [ha-addons-Repository](https://github.com/bborchers/ha-addons):

```text
<type>(<scope>): <beschreibung>
```

Beispiele:

```text
feat(stream): add Stream AC Pro telemetry
fix(mqtt): handle reconnect availability
docs(readme): document HACS installation
ci: validate conventional commits
```

Pull Requests werden automatisch mit Commitlint geprüft. Der `main`-Branch ist geschützt; Änderungen werden ausschließlich über Pull Requests übernommen. Nach einem Merge aktualisiert Release Drafter das nächste Release und veröffentlicht es automatisch.

## Lizenz und Herkunft

Die Integration steht unter MIT-Lizenz. Protokollkenntnisse und Gerätemappings basieren teilweise auf dem MIT-lizenzierten Projekt [foxthefox/ioBroker.ecoflow-mqtt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt). Die Integration ist nicht mit EcoFlow verbunden oder von EcoFlow freigegeben.
