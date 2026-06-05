"""
PDF report generator for protein/mutation research reports.

Uses ReportLab (pure Python, no external binaries like wkhtmltopdf).
Generates a clean, structured PDF from a ReportResponse object.

Design choices:
  - Single-pass layout using ReportLab Platypus (flowable-based)
  - Dark-on-white theme to match recruiter expectations for downloadable docs
  - Section-by-section layout: header, summary stats, mutation analysis,
    domains, disease associations, similar proteins, ClinVar, footer
  - All text is selectable (not rasterized) — important for research docs
"""

import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Colors matching the platform's #00ffaa-on-dark theme, adapted for print
DARK = (0.03, 0.04, 0.08)          # #080b14 equivalent
ACCENT = (0.0, 1.0, 0.67)          # #00ffaa — too bright for print
ACCENT_PRINT = (0.05, 0.55, 0.38)  # darker teal for print readability
LIGHT_BG = (0.95, 0.98, 0.96)      # very light green tint for section headers
MID_GRAY = (0.45, 0.45, 0.45)
LIGHT_GRAY = (0.85, 0.85, 0.85)
WHITE = (1, 1, 1)
RED_SOFT = (0.75, 0.15, 0.15)
GREEN_SOFT = (0.1, 0.55, 0.25)


def generate_report_pdf(report_data: dict) -> bytes:
    """
    Generate a PDF report from report data dict.
    Returns raw PDF bytes.

    Args:
        report_data: dict matching ReportResponse schema

    Returns:
        bytes: PDF file content
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    except ImportError:
        raise RuntimeError("reportlab is not installed. Run: pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Protein Report: {report_data.get('gene_name', 'Unknown')}",
        author="Protein Intelligence Platform",
    )

    rl_accent = colors.Color(*ACCENT_PRINT)
    rl_dark = colors.Color(*DARK)
    rl_light_bg = colors.Color(*LIGHT_BG)
    rl_mid_gray = colors.Color(*MID_GRAY)
    rl_light_gray = colors.Color(*LIGHT_GRAY)
    rl_red = colors.Color(*RED_SOFT)
    rl_green = colors.Color(*GREEN_SOFT)

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "PIPTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=rl_dark,
        spaceAfter=4,
        leading=26,
    )
    subtitle_style = ParagraphStyle(
        "PIPSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=rl_mid_gray,
        spaceAfter=2,
    )
    section_header_style = ParagraphStyle(
        "PIPSection",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=rl_accent,
        spaceBefore=12,
        spaceAfter=6,
        leading=14,
        borderPad=4,
    )
    body_style = ParagraphStyle(
        "PIPBody",
        parent=styles["Normal"],
        fontSize=9,
        textColor=rl_dark,
        spaceAfter=4,
        leading=13,
    )
    small_style = ParagraphStyle(
        "PIPSmall",
        parent=styles["Normal"],
        fontSize=8,
        textColor=rl_mid_gray,
        spaceAfter=2,
        leading=11,
    )
    mono_style = ParagraphStyle(
        "PIPMono",
        parent=styles["Code"],
        fontSize=7,
        textColor=rl_dark,
        backColor=rl_light_bg,
        spaceAfter=4,
        leading=10,
        leftIndent=4,
        rightIndent=4,
        borderPad=3,
    )

    story = []
    gene = report_data.get("gene_name", "Unknown")
    mutation = report_data.get("mutation_str")
    protein = report_data.get("protein") or {}
    mutation_data = report_data.get("mutation") or {}
    structure = report_data.get("structure") or {}
    similar = report_data.get("similar_proteins") or []
    clinvar = report_data.get("clinvar") or []
    generated_at = report_data.get("generated_at", datetime.utcnow())

    # ── Header ────────────────────────────────────────────────────────────────
    title_text = f"{gene}" + (f" · {mutation}" if mutation else "")
    story.append(Paragraph(title_text, title_style))
    story.append(Paragraph(
        protein.get("protein_name") or "Protein Intelligence Platform Report",
        subtitle_style
    ))
    story.append(Paragraph(
        f"Organism: {protein.get('organism', 'Homo sapiens')} &nbsp;·&nbsp; "
        f"UniProt: {protein.get('uniprot_id', 'N/A')} &nbsp;·&nbsp; "
        f"Generated: {generated_at if isinstance(generated_at, str) else generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        small_style
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=rl_accent, spaceAfter=8))

    # ── Summary stats row ────────────────────────────────────────────────────
    seq_len = protein.get("sequence_length") or "N/A"
    mass = protein.get("mass_da")
    mass_str = f"{mass/1000:.1f} kDa" if mass else "N/A"
    n_domains = len(protein.get("domains") or [])
    n_diseases = len(protein.get("disease_annotations") or [])

    stats_data = [
        ["Sequence length", "Molecular mass", "Domains", "Disease associations"],
        [
            f"{seq_len:,} aa" if isinstance(seq_len, int) else seq_len,
            mass_str,
            str(n_domains),
            str(n_diseases),
        ]
    ]
    stats_table = Table(stats_data, colWidths=["25%", "25%", "25%", "25%"])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_light_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_mid_gray),
        ("TEXTCOLOR", (0, 1), (-1, 1), rl_dark),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [rl_light_bg, WHITE]),
        ("BOX", (0, 0), (-1, -1), 0.5, rl_light_gray),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, rl_light_gray),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 8))

    # ── Function summary ─────────────────────────────────────────────────────
    func = protein.get("function_summary")
    if func:
        story.append(Paragraph("Function", section_header_style))
        story.append(Paragraph(func[:800], body_style))

    # ── Mutation analysis ────────────────────────────────────────────────────
    if mutation_data:
        story.append(Paragraph("Mutation Analysis", section_header_style))
        parse = mutation_data.get("parse") or {}

        is_pathogenic = mutation_data.get("is_known_pathogenic", False)
        path_text = (
            '<font color="#991f1f">⚠ Known pathogenic variant</font>'
            if is_pathogenic
            else '<font color="#1a8c46">✓ No known pathogenicity</font>'
        )
        story.append(Paragraph(path_text, body_style))

        if parse.get("valid"):
            story.append(Paragraph(
                f"{parse.get('original_aa_full', '')} (position {parse.get('position', '')}) → "
                f"{parse.get('mutated_aa_full', '')}",
                body_style
            ))

        prop_data = [
            ["Property", "Change"],
            ["Charge", mutation_data.get("charge_change") or "N/A"],
            ["Polarity", mutation_data.get("polarity_change") or "N/A"],
            ["Size", mutation_data.get("size_change") or "N/A"],
            ["Hydrophobicity", mutation_data.get("hydrophobicity_change") or "N/A"],
            ["Domain context", mutation_data.get("domain") or "Outside annotated domains"],
        ]
        prop_table = Table(prop_data, colWidths=["30%", "70%"])
        prop_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_light_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_mid_gray),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, rl_light_bg]),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_light_gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, rl_light_gray),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(prop_table)
        story.append(Spacer(1, 4))

        predicted = mutation_data.get("predicted_effect")
        if predicted:
            story.append(Paragraph(f"<i>{predicted}</i>", body_style))

    # ── Domains ──────────────────────────────────────────────────────────────
    domains = protein.get("domains") or []
    if domains:
        story.append(Paragraph(f"Domains & Features ({len(domains)})", section_header_style))
        dom_data = [["Type", "Name", "Position"]]
        for d in domains[:10]:
            start = d.get("start") or ""
            end = d.get("end") or ""
            pos = f"{start}–{end}" if start and end else "N/A"
            dom_data.append([
                d.get("type", "")[:20],
                d.get("name", "")[:40],
                pos,
            ])
        dom_table = Table(dom_data, colWidths=["20%", "55%", "25%"])
        dom_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_light_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_mid_gray),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, rl_light_bg]),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_light_gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, rl_light_gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(dom_table)

    # ── Disease associations ──────────────────────────────────────────────────
    diseases = protein.get("disease_annotations") or []
    if diseases:
        story.append(Paragraph(f"Disease Associations ({len(diseases)})", section_header_style))
        for d in diseases[:5]:
            story.append(Paragraph(
                f"<b>{d.get('name', '')}</b>: {d.get('description', '')[:200]}",
                body_style
            ))

    # ── Structure ────────────────────────────────────────────────────────────
    if structure:
        story.append(Paragraph("3D Structure", section_header_style))
        conf = structure.get("confidence_score")
        method = structure.get("method") or "AlphaFold"
        pdb_id = structure.get("pdb_id") or "N/A"
        res = structure.get("resolution_angstrom")
        lines = [
            f"Method: {method}",
            f"PDB ID: {pdb_id}",
        ]
        if conf:
            lines.append(f"AlphaFold pLDDT confidence: {conf:.1f}/100")
        if res:
            lines.append(f"Resolution: {res:.2f} Å")
        if structure.get("alphafold_pdb_url"):
            lines.append(f"Structure URL: {structure['alphafold_pdb_url']}")
        for line in lines:
            story.append(Paragraph(line, body_style))

    # ── Similar proteins ──────────────────────────────────────────────────────
    if similar:
        story.append(Paragraph(f"Similar Proteins (ESM2 + FAISS)", section_header_style))
        sim_data = [["Rank", "Gene", "Protein name", "Similarity"]]
        for i, sp in enumerate(similar[:8], 1):
            sim_data.append([
                str(i),
                sp.get("gene_name", ""),
                (sp.get("protein_name") or "")[:40],
                f"{sp.get('similarity_score', 0)*100:.1f}%",
            ])
        sim_table = Table(sim_data, colWidths=["8%", "15%", "57%", "20%"])
        sim_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_light_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_mid_gray),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, rl_light_bg]),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_light_gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, rl_light_gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ]))
        story.append(sim_table)

    # ── ClinVar ──────────────────────────────────────────────────────────────
    if clinvar:
        story.append(Paragraph(f"ClinVar Variants ({len(clinvar)})", section_header_style))
        cv_data = [["Significance", "Disease", "Variant ID", "Status"]]
        for cv in clinvar[:6]:
            sig = cv.get("clinical_significance") or "Unknown"
            cv_data.append([
                sig[:25],
                (cv.get("disease_name") or "")[:35],
                cv.get("variant_id") or "N/A",
                (cv.get("review_status") or "")[:20],
            ])
        cv_table = Table(cv_data, colWidths=["22%", "38%", "18%", "22%"])
        cv_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_light_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_mid_gray),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, rl_light_bg]),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_light_gray),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, rl_light_gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cv_table)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=rl_light_gray))
    story.append(Paragraph(
        "Generated by Protein Intelligence Platform · "
        "Data sources: UniProt, AlphaFold DB, RCSB PDB, NCBI ClinVar · "
        "Not for clinical use.",
        small_style
    ))

    doc.build(story)
    return buffer.getvalue()
