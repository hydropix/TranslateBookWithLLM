# Watermarking System (PRIVÉ - NON VERSIONNÉ)

Ce dossier contient le système de watermarking et les outils de détection.

**IMPORTANT : Ne pas partager publiquement. Garder discret.**

## Fichiers

### Tests
- `test_watermarking.py` - Tests des watermarks HTTP
- `test_steganography.py` - Tests watermarking stéganographique

### Outils
- `detect_watermark.py` - Détection de watermarks dans fichiers traduits

## Usage

### Tester le système
```bash
python .watermark/test_watermarking.py
python .watermark/test_steganography.py
```

### Détecter dans un fichier suspect
```bash
python .watermark/detect_watermark.py fichier_suspect.epub
python .watermark/detect_watermark.py fichier_suspect.txt
```

## Watermarks Actifs

### 1. HTTP Headers (Toujours Actif)
Tous les appels API incluent :
- `X-Translation-Engine: TranslateBookWithLLM/1.0.0`
- `X-Client-Instance: {instance_id}`
- `X-Session-ID: {session_id}`

**Implémentation** : `src/core/llm_providers.py`

### 2. Stéganographie (À Activer)
Caractères zero-width invisibles dans traductions.

**Pour activer** :
```bash
# Dans .env
STEGANOGRAPHIC_WATERMARK_ENABLED=true
```

**Implémentation** : `src/utils/steganography.py`

**Intégration** : À ajouter dans `src/core/translator.py` ou `post_processor.py`

### 3. Debug Markers
Markers hex dans logs DEBUG : `[0x{instance_id}]`

**Implémentation** : `src/utils/unified_logger.py`

## Détection Externe

### Méthode 1 : Watermark Stéganographique (MEILLEUR)
1. Télécharger un fichier traduit par service suspect
2. `python .watermark/detect_watermark.py fichier.epub`
3. Si détecté → preuve irréfutable

### Méthode 2 : Recherche GitHub
```
site:github.com "X-Translation-Engine: TranslateBookWithLLM"
site:github.com "src/core/llm_providers.py"
```

### Méthode 3 : Messages d'Erreur
Tester avec fichiers invalides, chercher stack traces Python révélant :
- `src/core/translator.py`
- `src/core/epub/simplified_translator.py`

## Actions Si Violation Détectée

1. **Documenter** : Screenshots, fichiers, timestamps
2. **Contact amical** : Email expliquant AGPL-3.0
3. **Escalade** : Cease & desist si refus
4. **DMCA** : Si hébergé USA
5. **Juridique** : En dernier recours

## Sécurité

- ✅ Ce dossier est dans `.gitignore` (non versionné)
- ✅ Ne jamais commit publiquement
- ✅ Ne pas partager stratégie de détection
- ✅ Garder discret pour efficacité maximale

## Notes

Le watermarking est **transparent** pour utilisateurs légitimes :
- Zéro impact performance
- Zéro impact visuel
- Zéro télémétrie
- Respect total vie privée

Sert uniquement à détecter violations AGPL-3.0 post-facto.
