# Release Checklist

1. Update `custom_components/finance_portfolio/manifest.json` version.
2. Run checks:

```bash
python3 -m py_compile custom_components/finance_portfolio/*.py
node --check custom_components/finance_portfolio/www/finance-portfolio-card.js
```

3. Commit changes.
4. Create and push a tag:

```bash
git tag v0.2.0
git push origin main --tags
```

5. Create a GitHub release from the tag.
