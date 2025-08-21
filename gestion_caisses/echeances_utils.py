from io import BytesIO
from datetime import datetime
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from .utils import get_parametres_application, create_standard_header, create_standard_footer


def generate_echeances_retard_pdf(caisse=None):
    """Génère un PDF moderne de rapport des échéances en retard."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    # Récupérer les paramètres de l'application
    parametres = get_parametres_application()
    
    # Styles modernes
    styles = getSampleStyleSheet()
    
    # Style de section
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.HexColor('#F18F01'),
        fontName='Helvetica-Bold'
    )
    
    # En-tête standard avec logo, nom de l'application et informations
    subtitle = f"Caisse: {caisse.nom_association}" if caisse else "Toutes les caisses"
    create_standard_header(story, parametres, "RAPPORT DES ÉCHÉANCES EN RETARD", subtitle)
    
    # Informations de la caisse
    if caisse:
        story.append(Paragraph(f"📋 CAISSE: {caisse.nom_association}", section_style))
        caisse_info = [
            ["Code de la caisse:", caisse.code],
            ["Région:", caisse.region.nom if caisse.region else "Non définie"],
            ["Préfecture:", caisse.prefecture.nom if caisse.prefecture else "Non définie"],
            ["Commune:", caisse.commune.nom if caisse.commune else "Non définie"],
            ["Date du rapport:", timezone.now().strftime('%d/%m/%Y à %H:%M')]
        ]
        
        caisse_table = Table(caisse_info, colWidths=[2.5*inch, 4*inch])
        caisse_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4FD')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))
        
        story.append(caisse_table)
        story.append(Spacer(1, 20))
    
    # Récupérer les échéances en retard
    from .models import Echeance, Pret
    
    today = timezone.now().date()
    
    if caisse:
        echeances_retard = Echeance.objects.filter(
            pret__caisse=caisse,
            date_echeance__lt=today,
            statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
        ).select_related('pret', 'pret__membre').order_by('date_echeance')
    else:
        echeances_retard = Echeance.objects.filter(
            date_echeance__lt=today,
            statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
        ).select_related('pret', 'pret__membre', 'pret__caisse').order_by('date_echeance')
    
    # Statistiques
    total_echeances_retard = echeances_retard.count()
    montant_total_retard = sum(e.montant_echeance for e in echeances_retard)
    prets_concernes = echeances_retard.values('pret').distinct().count()
    
    story.append(Paragraph("📊 STATISTIQUES GÉNÉRALES", section_style))
    
    stats_info = [
        ["Nombre total d'échéances en retard:", f"{total_echeances_retard}"],
        ["Montant total en retard:", f"{montant_total_retard:,.0f} FCFA"],
        ["Nombre de prêts concernés:", f"{prets_concernes}"],
        ["Date de génération:", today.strftime('%d/%m/%Y')]
    ]
    
    stats_table = Table(stats_info, colWidths=[3*inch, 3.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8D7DA')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DC3545')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Détail des échéances en retard
    if echeances_retard.exists():
        story.append(Paragraph("🔴 DÉTAIL DES ÉCHÉANCES EN RETARD", section_style))
        
        echeances_headers = ["Membre", "N° Prêt", "N° Échéance", "Date échéance", "Jours retard", "Montant", "Caisse"]
        echeances_data = [echeances_headers]
        
        for echeance in echeances_retard:
            jours_retard = (today - echeance.date_echeance).days
            
            echeances_data.append([
                echeance.pret.membre.nom_complet,
                echeance.pret.numero_pret,
                f"Échéance {echeance.numero_echeance}",
                echeance.date_echeance.strftime('%d/%m/%Y'),
                f"{jours_retard} jours",
                f"{echeance.montant_echeance:,.0f} FCFA",
                echeance.pret.caisse.nom_association if not caisse else ""
            ])
        
        # Ajuster les largeurs de colonnes selon le contexte
        if caisse:
            col_widths = [2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch, 1.2*inch]
        else:
            col_widths = [1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch, 1.2*inch, 1.4*inch]
        
        echeances_table = Table(echeances_data, colWidths=col_widths)
        echeances_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC3545')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DC3545')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))
        
        story.append(echeances_table)
    else:
        story.append(Paragraph("✅ AUCUNE ÉCHÉANCE EN RETARD", section_style))
        story.append(Paragraph(
            "Toutes les échéances sont à jour. Aucun retard constaté.",
            ParagraphStyle(
                'Success',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#28A745'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
        ))
    
    story.append(Spacer(1, 20))
    
    # Recommandations
    story.append(Paragraph("💡 RECOMMANDATIONS", section_style))
    
    recommendations_text = f"""
    <b>Actions recommandées :</b><br/>
    • Contacter immédiatement les membres en retard de paiement<br/>
    • Envoyer des rappels par téléphone ou SMS<br/>
    • Organiser des réunions de sensibilisation<br/>
    • Mettre en place un système de suivi renforcé<br/>
    • Considérer des mesures d'accompagnement pour les cas difficiles<br/><br/>
    
    <b>Prévention :</b><br/>
    • Renforcer la communication sur les échéances<br/>
    • Mettre en place des alertes automatiques<br/>
    • Former les membres sur la gestion financière<br/>
    • Établir des procédures de suivi régulier
    """
    
    story.append(Paragraph(recommendations_text, ParagraphStyle(
        'Recommendations',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        leftIndent=20,
        rightIndent=20,
        fontName='Helvetica'
    )))
    
    # Ajouter les signatures
    story.append(Spacer(1, 30))
    story.append(Paragraph("✍️ SIGNATURES", section_style))
    
    # Récupérer le président général actif
    try:
        from .models import PresidentGeneral
        president_general = PresidentGeneral.objects.filter(statut='ACTIF').first()
    except:
        president_general = None
    
    signatures_data = []
    
    # Président Général
    if president_general:
        if hasattr(president_general, 'signature') and president_general.signature:
            try:
                sig_pg = Image(president_general.signature.path, width=1*inch, height=0.5*inch)
            except:
                sig_pg = "Signature non disponible"
        else:
            sig_pg = "Signature non disponible"
        
        signatures_data.append([
            "Président Général:",
            sig_pg,
            president_general.nom_complet
        ])
    else:
        signatures_data.append([
            "Président Général:",
            "Non défini",
            "Non défini"
        ])
    
    # Présidente de la caisse
    if caisse and caisse.presidente:
        if hasattr(caisse.presidente, 'signature') and caisse.presidente.signature:
            try:
                sig_pres = Image(caisse.presidente.signature.path, width=1*inch, height=0.5*inch)
            except:
                sig_pres = "Signature non disponible"
        else:
            sig_pres = "Signature non disponible"
        
        signatures_data.append([
            "Présidente de la caisse:",
            sig_pres,
            caisse.presidente.nom_complet
        ])
    else:
        signatures_data.append([
            "Présidente de la caisse:",
            "Non définie",
            "Non définie"
        ])
    
    # Créer le tableau des signatures
    signatures_table = Table(signatures_data, colWidths=[2.5*inch, 2*inch, 2*inch])
    signatures_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4FD')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#2E86AB')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
    ]))
    
    story.append(signatures_table)
    story.append(Spacer(1, 20))
    
    # Pied de page standard avec informations du PDG
    create_standard_footer(story, parametres)
    
    # Construire le PDF
    doc.build(story)
    
    # Récupérer le contenu du buffer
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content
