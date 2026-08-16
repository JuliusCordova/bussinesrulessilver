from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ProfileReportService:
    """Build a governed PDF exclusively from canonical BigQuery profile evidence."""

    def build(self, profile: dict[str, Any]) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title=f"Perfilamiento Silver - {profile.get('table', '')}",
            author="Business Rules Silver",
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "ProfileTitle",
            parent=styles["Title"],
            textColor=colors.HexColor("#202020"),
            alignment=TA_CENTER,
            spaceAfter=8,
        )
        heading = ParagraphStyle(
            "ProfileHeading",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#c62828"),
            spaceBefore=8,
            spaceAfter=6,
        )
        small = ParagraphStyle(
            "ProfileSmall",
            parent=styles["BodyText"],
            fontSize=7.4,
            leading=9,
        )

        table_name = escape(str(profile.get("table") or "No informada"))
        row_count = int(profile.get("row_count", 0) or 0)
        columns = list(profile.get("columns") or [])
        key_candidates = [str(value) for value in profile.get("business_key_candidates") or []]
        critical_columns = [str(value) for value in profile.get("critical_columns") or []]

        story = [
            Paragraph("Informe de perfilamiento de tabla origen", title),
            Paragraph(f"<b>Tabla:</b> {table_name}", styles["BodyText"]),
            Spacer(1, 5),
            self._summary_table(row_count, columns, key_candidates, critical_columns),
            Spacer(1, 8),
            Paragraph("Conclusiones de inferencia", heading),
            Paragraph(
                self._inference_text(profile, key_candidates),
                styles["BodyText"],
            ),
            Spacer(1, 8),
            Paragraph("Detalle por columna", heading),
        ]

        rows = [[
            Paragraph("<b>Columna</b>", small),
            Paragraph("<b>Tipo</b>", small),
            Paragraph("<b>Modo</b>", small),
            Paragraph("<b>Nulos</b>", small),
            Paragraph("<b>% nulos</b>", small),
            Paragraph("<b>Distintos</b>", small),
            Paragraph("<b>% unicidad</b>", small),
            Paragraph("<b>Evidencia</b>", small),
        ]]
        for column in columns:
            null_ratio = float(column.get("null_ratio", 0) or 0)
            unique_ratio = float(column.get("unique_ratio", 0) or 0)
            evidence = []
            if column.get("business_key_candidate"):
                evidence.append("Clave candidata: sin nulos y cardinalidad igual a filas")
            if column.get("critical_candidate"):
                evidence.append("Campo critico por contrato/nombre")
            if not evidence:
                evidence.append("Columna perfilada")
            rows.append([
                Paragraph(escape(str(column.get("name") or "")), small),
                Paragraph(escape(str(column.get("type") or "")), small),
                Paragraph(escape(str(column.get("mode") or "")), small),
                f"{int(column.get('null_count', 0) or 0):,}",
                f"{null_ratio:.2%}",
                f"{int(column.get('distinct_count', 0) or 0):,}",
                f"{unique_ratio:.2%}",
                Paragraph(escape("; ".join(evidence)), small),
            ])

        detail = Table(
            rows,
            repeatRows=1,
            colWidths=[38 * mm, 22 * mm, 19 * mm, 20 * mm, 19 * mm, 22 * mm, 21 * mm, 80 * mm],
        )
        detail.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ff342e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d2c9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f6f4")]),
            ("FONTSIZE", (0, 1), (-1, -1), 7.4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(detail)
        story.extend([
            Spacer(1, 8),
            Paragraph(
                "Fuente: metricas deterministicas consultadas en BigQuery. "
                "Las recomendaciones requieren confirmacion humana antes de generar artefactos.",
                small,
            ),
        ])

        document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return buffer.getvalue()

    @staticmethod
    def _summary_table(
        row_count: int,
        columns: list[dict[str, Any]],
        keys: list[str],
        critical: list[str],
    ) -> Table:
        data = [
            ["Filas", "Columnas", "Claves candidatas", "Campos criticos"],
            [f"{row_count:,}", str(len(columns)), str(len(keys)), str(len(critical))],
        ]
        table = Table(data, colWidths=[58 * mm] * 4)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef5ff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2459b2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 14),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#bed2f6")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d2c9")),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    @staticmethod
    def _inference_text(profile: dict[str, Any], keys: list[str]) -> str:
        partitioning = profile.get("partitioning")
        if keys:
            strategy = (
                f"MERGE es viable porque BigQuery evidencio la(s) clave(s) candidata(s) "
                f"{escape(', '.join(keys))}: cero nulos y unicidad compatible con el total de filas."
            )
        else:
            strategy = (
                "FULL es la opcion segura inicial porque el perfil no encontro una clave candidata "
                "con cero nulos y unicidad suficiente. MERGE requiere seleccion humana de una clave."
            )
        watermark = (
            f" Particion observada: {escape(str(partitioning))}."
            if partitioning
            else " No se observo una columna de particion en la tabla."
        )
        return strategy + watermark

    @staticmethod
    def _footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#65605c"))
        canvas.drawString(14 * mm, 8 * mm, "Business Rules Silver - Evidencia de perfilamiento")
        canvas.drawRightString(
            landscape(A4)[0] - 14 * mm,
            8 * mm,
            f"Pagina {document.page}",
        )
        canvas.restoreState()
