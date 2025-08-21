import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def build_paragraph(text, style_name="BodyText"):
    styles = getSampleStyleSheet()
    return Paragraph(text, styles[style_name])


def main():
    base_dir = os.path.dirname(__file__)
    out_path = os.path.join(base_dir, "deployment_guide.pdf")

    doc = SimpleDocTemplate(out_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []

    title = build_paragraph("<b>Guide de Déploiement - Application Django caisses_femmes</b>", "Title")
    elements.append(title)
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Hébergeurs recommandés (rapides)</b>"))
    elements.append(build_paragraph("- <b>Render</b>: déploiement Docker, Postgres managé, SSL, simplicité."))
    elements.append(build_paragraph("- <b>Fly.io</b>: très performant, déploiement Docker, volumes, anycast."))
    elements.append(build_paragraph("- <b>Railway</b>: setup rapide, Postgres/Redis managés, variables d'env faciles."))
    elements.append(build_paragraph("- <b>Hetzner Cloud</b>: VPS économique et rapide (Nginx + Docker Compose)."))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Pré-requis</b>"))
    elements.append(build_paragraph("- Variables d'environnement: SECRET_KEY, DEBUG=False, DB_*, REDIS_URL, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS."))
    elements.append(build_paragraph("- Base de données PostgreSQL accessible depuis l'app."))
    elements.append(build_paragraph("- Certificat TLS (ou SSL managé par l'hébergeur)."))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Étapes de déploiement (Docker Compose)</b>"))
    steps = [
        "1. Construire l'image: docker build -t caisses-femmes .",
        "2. Configurer .env (SECRET_KEY, DB_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS).",
        "3. Lancer: docker compose up -d --build",
        "4. Appliquer les migrations: docker compose exec web python manage.py migrate",
        "5. Créer le superuser: docker compose exec web python manage.py createsuperuser",
        "6. Collecter les statiques si nécessaire: docker compose exec web python manage.py collectstatic --noinput",
        "7. Vérifier Nginx: http(s)://votre-domaine/",
    ]
    for s in steps:
        elements.append(build_paragraph(s))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Configuration Django</b>"))
    elements.append(build_paragraph("- Utiliser USE_X_FORWARDED_PROTO=true derrière Nginx."))
    elements.append(build_paragraph("- Définir ALLOWED_HOSTS à votre domaine (ex: app.exemple.com)."))
    elements.append(build_paragraph("- CSRF_TRUSTED_ORIGINS: https://app.exemple.com"))
    elements.append(build_paragraph("- SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE activés en prod (déjà gérés)."))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Base de données</b>"))
    elements.append(build_paragraph("- Variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD."))
    elements.append(build_paragraph("- Sauvegardes régulières (pg_dump)."))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Certificats TLS</b>"))
    elements.append(build_paragraph("- Avec nginx: montez /etc/nginx/ssl avec cert.pem et key.pem."))
    elements.append(build_paragraph("- Ou utilisez un reverse proxy/hébergeur avec SSL managé."))
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Commandes utiles</b>"))
    cmds = Table([
        ["Migrations", "docker compose exec web python manage.py migrate"],
        ["Superuser", "docker compose exec web python manage.py createsuperuser"],
        ["Collect static", "docker compose exec web python manage.py collectstatic --noinput"],
        ["Shell", "docker compose exec web python manage.py shell"],
        ["Logs web", "docker compose logs -f web"],
        ["Logs nginx", "docker compose logs -f nginx"],
    ], colWidths=[120, 360])
    cmds.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(cmds)
    elements.append(Spacer(1, 12))

    elements.append(build_paragraph("<b>Conseils performance</b>"))
    elements.append(build_paragraph("- 3 workers Gunicorn (ajustez selon CPU)."))
    elements.append(build_paragraph("- Activez le cache Redis pour composants coûteux si nécessaire."))
    elements.append(build_paragraph("- Activez GZip (déjà configuré) et headers de cache statiques (Nginx)."))

    doc.build(elements)
    print(f"PDF généré: {out_path}")


if __name__ == "__main__":
    main()


