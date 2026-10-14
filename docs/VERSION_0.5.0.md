# WebSnapshot 0.5.0 – Erfassungsprofile

Version 0.5.0 bereitet die Erfassung dynamischer Websites vor. Unter «Websites verwalten» lässt sich für jede Website der Erfassungsmodus auswählen. Statisch ist standardmässig aktiviert und funktioniert wie bisher. Browser ist vorerst eine gespeicherte Konfiguration und kann nicht ausgeführt werden.

Für den späteren Browsermodus lassen sich ein CSS-Selektor und eine Wartezeit festlegen. Die Einstellungen werden in der SQLite-Datenbank gespeichert. Ein Browser-Snapshot wird vor dem Erstellen eines Jobs abgelehnt; eine unbemerkte statische Erfassung erfolgt nicht.

In Version 0.6.0 folgen Playwright, Chromium und die Erfassung gerenderter dynamischer Seiten. Version 0.5.0 benötigt keine zusätzlichen Browser-Abhängigkeiten.
