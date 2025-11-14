# BWT Monservice - Home Assistant Integration

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024+-blue.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)

Une intégration Home Assistant personnalisée pour monitorer les adoucisseurs d'eau BWT via le portail BWT MonService.

![BWT MonService logo](https://www.bwt-monservice.com/build/images/logo.png)

## > ⚠️ **Cette intégration ne fonctionne seulement avec le site https://bwt-monservice.com**

## Fonctionnalités

### Multilingual Support

L'intégration supporte plusieurs langues et s'adapte automatiquement à la langue configurée dans Home Assistant:

- **English** (default)
- **Français**

Les noms des sensors et binary sensors sont automatiquement traduits selon la langue système.

### Sensors (12)

- 💧 **Consommation d'eau** - Volume d'eau consommé aujourd'hui (L)
- 🔄 **Régénérations** - Nombre de régénérations aujourd'hui
- 📊 **Dureté d'entrée** - Dureté de l'eau en entrée (°f)
- 📉 **Dureté de sortie** - Dureté de l'eau en sortie (°f)
- 🔧 **Pression réseau** - Pression du réseau d'eau (bar)
- 🕐 **Dernière connexion** - Horodatage de la dernière connexion de l'appareil
- 🔢 **Numéro de série** - Numéro de série de l'appareil
- 📅 **Mise en service** - Date d'installation de l'appareil
- ✈️ **Mode vacances** - Statut du mode vacances (Actif/Inactif)
- 🧂 **Type de sel** - Type de sel configuré (Tablettes/Grains)
- ⏰ **Heure régénération** - Heure de début de régénération programmée
- 📶 **Signal WiFi** - Puissance du signal WiFi (dBm)

### Binary Sensors (5)

- ✅ **Connecté** - Statut de connexion WiFi de l'appareil
- 🌐 **En ligne** - Appareil en ligne sur le réseau
- 🔌 **Connectable** - Appareil accessible
- ⚡ **Coupure de courant** - Coupure de courant détectée aujourd'hui
- 🚨 **Alarme sel** - Niveau de sel bas détecté

## Installation

### Méthode 1 : Installation manuelle

1. **Télécharger l'intégration**

   ```bash
   cd /config  # ou votre répertoire de configuration Home Assistant
   mkdir -p custom_components
   cd custom_components
   git clone https://github.com/calagan74/bwt_monservice.git
   ```

2. **Copier les fichiers**

   ```
   custom_components/
   └── bwt_monservice/
       ├── __init__.py
       ├── api.py
       ├── binary_sensor.py
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── manifest.json
       ├── sensor.py
       ├── icon.png
       ├── icon@2x.png
       └── translations/
           └── en.json
           └── fr.json
   ```

3. **Redémarrer Home Assistant**

### Méthode 2 : HACS (Home Assistant Community Store)

> ⚠️ Cette intégration n'est pas encore disponible dans le store HACS par défaut.

Pour l'ajouter comme repository personnalisé :

1. Ouvrir HACS → Intégrations
2. Menu ⋮ → Repositories personnalisés
3. Ajouter `https://github.com/calagan74/bwt_monservice`
4. Catégorie : Intégration
5. Installer "BWT MonService"
6. Redémarrer Home Assistant

## Configuration

### Première configuration

1. Aller dans **Paramètres** → **Appareils et Services**
2. Cliquer sur **+ Ajouter une intégration**
3. Rechercher **"BWT MonService"**
4. Saisir vos identifiants :
   - 📧 **Email** : votre adresse email BWT MonService
   - 🔑 **Mot de passe** : votre mot de passe BWT MonService

### Options de configuration

Après l'installation, vous pouvez configurer :

- **Intervalle de mise à jour** : 5 à 1440 minutes (par défaut : 10 minutes)

Pour modifier :

1. Aller dans **Paramètres** → **Appareils et Services**
2. Cliquer sur **BWT MonService**
3. Cliquer sur **Configurer**

## Prérequis

- **Home Assistant** : 2024.1.0 ou supérieur
- **Python** : 3.11 ou supérieur
- **Compte BWT MonService** : https://www.bwt-monservice.com

## Architecture technique

### Session persistante

L'intégration utilise une **session HTTP persistante** pour optimiser les performances :

- ✅ **1-2 secondes** par mise à jour (au lieu de 10-15 secondes)
- ✅ Authentification unique au démarrage
- ✅ Reconnexion automatique en cas d'expiration
- ✅ Charge serveur minimale

### Sources de données

1. **Endpoint AJAX** : Données temps réel (consommation, régénérations, alarmes)
2. **Scraping HTML** : Données de configuration (dureté, pression, paramètres)

## Dépannage

### L'intégration ne se charge pas

1. Vérifier les logs : **Paramètres** → **Système** → **Journaux**
2. Activer les logs de débogage dans `configuration.yaml` :
   ```yaml
   logger:
     default: info
     logs:
       custom_components.bwt_monservice: debug
   ```
3. Redémarrer Home Assistant

### Les données ne se mettent pas à jour

- Vérifier votre connexion internet
- Vérifier que le site BWT MonService est accessible
- Vérifier vos identifiants (email/mot de passe)
- Augmenter l'intervalle de mise à jour si le serveur est lent

### Erreur d'authentification

- Vérifier vos identifiants sur https://www.bwt-monservice.com
- Réinitialiser votre mot de passe si nécessaire
- Supprimer et reconfigurer l'intégration

## Utilisation avancée

### Créer un compteur total de régénérations

Ajouter dans `configuration.yaml` :

```yaml
utility_meter:
  bwt_regenerations_total:
    source: sensor.bwt_regenerations_today
    cycle: none
    name: "Régénérations totales"

  bwt_regenerations_monthly:
    source: sensor.bwt_regenerations_today
    cycle: monthly
    name: "Régénérations ce mois"
```

### Dashboard exemple

```yaml
type: entities
title: BWT Adoucisseur
entities:
  - entity: sensor.bwt_water_consumption
    name: Consommation du jour
  - entity: sensor.bwt_regenerations_today
    name: Régénérations aujourd'hui
  - entity: sensor.bwt_hardness_out
    name: Dureté sortie
  - entity: binary_sensor.bwt_salt_alarm
    name: Niveau de sel
  - entity: sensor.bwt_holiday_mode
    name: Mode vacances
```

## Limitations connues

- ❌ **Lecture seule** : Impossible de contrôler l'appareil (activer mode vacances, forcer régénération, **mais c'est voulu**)
- ❌ **Un seul appareil** : Supporte uniquement le premier appareil du compte
- ❌ **Données du jour** : Historique limité aux données d'aujourd'hui (c'est HA qui historise)
- ⏱️ **Serveur lent** : Le serveur BWT **EST** lent (10-15 secondes lors de la première connexion)

## Contribuer

Les contributions sont les bienvenues ! Pour contribuer :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

### Adding Translations

To add support for a new language:

1. Create a new translation file `translations/<language_code>.json`
2. Follow the structure of existing translation files (`en.json` or `fr.json`)
3. Add translations for all keys in the `config`, `options`, and `entity` sections

Example structure:

```json
{
  "config": { ... },
  "options": { ... },
  "entity": {
    "sensor": {
      "water_consumption": {
        "name": "Your translation"
      },
      ...
    },
    "binary_sensor": {
      "connected": {
        "name": "Your translation"
      },
      ...
    }
  }
}
```

## Support

- 🐛 **Signaler un bug** : [Issues GitHub](https://github.com/calagan74/bwt_monservice/issues)
- 💬 **Discussions** : [GitHub Discussions](https://github.com/calagan74/bwt_monservice/discussions)
- 📖 **Documentation** : [CLAUDE.md](CLAUDE.md)

## Remerciements

- [Home Assistant](https://www.home-assistant.io/) - Plateforme domotique
- [BWT](https://www.bwt.com/) - Fabricant d'adoucisseurs d'eau
- Tous les contributeurs du projet

## Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

Made with ❤️ for the Home Assistant community
