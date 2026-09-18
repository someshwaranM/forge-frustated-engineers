"""
Vigil — RM Compliance Report HTML Renderer (backend/reports/rm_report_renderer.py)
Phase 15: Responsive, Email-Safe, Deterministic HTML & Plain-Text Report Generator

Strict constraints:
- Pure rendering: no DB queries, no network calls.
- Universal email-client compatibility (inline styles, table-based layout).
- Strict HTML escaping on all dynamic variables.
- Indic script font fallback stack for Devanagari & Tamil transcripts.
- Clean RM, Zero-call RM, and Violation states handled distinctly.
"""

import html
from typing import Dict, Any, List


def esc(value: Any) -> str:
    """Safely escape dynamic values for HTML insertion."""
    if value is None:
        return ""
    return html.escape(str(value))


def get_severity_colors(severity: str) -> Dict[str, str]:
    """Return inline CSS color definitions for severity badges."""
    sev = (severity or "").upper()
    if sev == "HIGH":
        return {
            "bg": "#fef2f2",
            "border": "#fecaca",
            "text": "#b91c1c",
            "pill_bg": "#dc2626",
            "pill_text": "#ffffff",
        }
    elif sev == "MEDIUM":
        return {
            "bg": "#fffbeb",
            "border": "#fde68a",
            "text": "#b45309",
            "pill_bg": "#f59e0b",
            "pill_text": "#ffffff",
        }
    elif sev == "LOW":
        return {
            "bg": "#eff6ff",
            "border": "#bfdbfe",
            "text": "#1d4ed8",
            "pill_bg": "#3b82f6",
            "pill_text": "#ffffff",
        }
    return {
        "bg": "#f8fafc",
        "border": "#e2e8f0",
        "text": "#475569",
        "pill_bg": "#64748b",
        "pill_text": "#ffffff",
    }


def render_rm_report_html(report_data: Dict[str, Any]) -> str:
    """
    Render authoritative report data into a responsive, table-based, email-safe HTML report.
    """
    rm = report_data.get("rm", {})
    metrics = report_data.get("metrics", {})
    status_eval = report_data.get("status_evaluation", {})
    calls = report_data.get("calls", [])
    findings = report_data.get("findings", [])
    cases = report_data.get("cases", [])
    report_id = report_data.get("report_id", "")
    generated_at = report_data.get("generated_at", "")
    app_url = report_data.get("app_url", "").strip().rstrip("/")

    rm_name = esc(rm.get("full_name", "Relationship Manager"))
    rm_id = esc(rm.get("rm_id", ""))
    branch = esc(rm.get("branch", ""))
    region = esc(rm.get("region", ""))
    manager_name = esc(rm.get("manager_name", "Branch Head"))
    joined_date = esc(rm.get("joined_date", ""))
    rm_email = esc(rm.get("email", ""))

    status_type = status_eval.get("status_type", "CLEAN")
    status_headline = esc(status_eval.get("headline", ""))
    status_summary = esc(status_eval.get("summary", ""))

    risk_score = metrics.get("risk_score", 0)
    risk_color = "#dc2626" if risk_score > 60 else "#f59e0b" if risk_score > 30 else "#10b981"

    # Status Banner Styling
    if status_type == "REPEAT_VIOLATIONS":
        status_bg = "#fef2f2"
        status_border = "#f87171"
        status_title_color = "#991b1b"
        status_icon = "&#9888;"
    elif status_type == "REVIEW_REQUIRED":
        status_bg = "#fffbeb"
        status_border = "#fcd34d"
        status_title_color = "#92400e"
        status_icon = "&#9888;"
    elif status_type == "NO_CALLS":
        status_bg = "#f0f9ff"
        status_border = "#bae6fd"
        status_title_color = "#075985"
        status_icon = "&#8505;"
    else:  # CLEAN
        status_bg = "#f0fdf4"
        status_border = "#86efac"
        status_title_color = "#166534"
        status_icon = "&#10003;"

    # Build Call Rows HTML
    call_rows_html = ""
    if calls:
        for c in calls:
            v_status = c.get("violation_status", "CLEAN")
            is_clean = v_status == "CLEAN"
            badge_bg = "#f0fdf4" if is_clean else "#fef2f2"
            badge_border = "#bbf7d0" if is_clean else "#fecaca"
            badge_text = "#166534" if is_clean else "#991b1b"

            call_rows_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="padding: 10px 12px; font-family: monospace; font-size: 12px; color: #0f172a; font-weight: 600;">{esc(c.get('call_id'))}</td>
              <td style="padding: 10px 12px; font-size: 13px; color: #334155;">{esc(c.get('customer_name'))}</td>
              <td style="padding: 10px 12px; font-size: 12px; color: #64748b;">{esc(c.get('date_time'))}</td>
              <td style="padding: 10px 12px; font-size: 12px; color: #475569;">{esc(c.get('language'))}</td>
              <td style="padding: 10px 12px; font-size: 12px; color: #475569; font-family: monospace;">{esc(c.get('duration_formatted'))}</td>
              <td style="padding: 10px 12px; text-align: right;">
                <span style="display: inline-block; padding: 3px 8px; font-size: 11px; font-weight: bold; font-family: monospace; border-radius: 4px; background-color: {badge_bg}; border: 1px solid {badge_border}; color: {badge_text};">
                  {esc(v_status)}
                </span>
              </td>
            </tr>
            """
    else:
        call_rows_html = """
        <tr>
          <td colspan="6" style="padding: 24px; text-align: center; color: #64748b; font-size: 13px;">
            No advisory calls have been indexed for this Relationship Manager.
          </td>
        </tr>
        """

    # Build Findings Cards HTML
    findings_cards_html = ""
    if findings:
        for f in findings:
            sev_colors = get_severity_colors(f.get("severity", "LOW"))
            source_link = ""
            if f.get("regulation_source_url"):
                source_link = f"""&middot; <a href="{esc(f.get('regulation_source_url'))}" target="_blank" style="color: #2563eb; text-decoration: underline;">Official Reference &rarr;</a>"""

            case_link = ""
            if f.get("case_id"):
                case_link = f"""&middot; <strong style="color: #475569;">Case:</strong> <span style="font-family: monospace; color: #0f172a;">{esc(f.get('case_id'))}</span> ({esc(f.get('case_status', 'OPEN'))})"""

            findings_cards_html += f"""
            <div style="margin-bottom: 20px; background-color: #ffffff; border: 1px solid #cbd5e1; border-left: 5px solid {sev_colors['pill_bg']}; border-radius: 6px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">
                <div>
                  <span style="display: inline-block; padding: 2px 8px; font-size: 11px; font-weight: bold; border-radius: 3px; background-color: {sev_colors['pill_bg']}; color: {sev_colors['pill_text']}; letter-spacing: 0.5px;">
                    {esc(f.get('severity'))} SEVERITY
                  </span>
                  <span style="font-size: 14px; font-weight: 700; color: #0f172a; margin-left: 8px;">
                    {esc(f.get('category'))}
                  </span>
                </div>
                <div style="font-size: 12px; color: #64748b; font-family: monospace;">
                  Conf: <strong>{esc(f.get('confidence_pct'))}%</strong>
                </div>
              </div>

              <div style="font-size: 12px; color: #475569; margin-bottom: 10px;">
                <strong>Call:</strong> <span style="font-family: monospace;">{esc(f.get('call_id'))}</span> &middot; 
                <strong>Timestamp:</strong> <span style="font-family: monospace;">{esc(f.get('timestamp_interval'))}</span>
                {case_link}
              </div>

              <!-- Evidence Quote -->
              <div style="margin: 10px 0; padding: 10px 14px; background-color: #f8fafc; border-left: 3px solid #94a3b8; font-style: italic; font-size: 13px; color: #1e293b; line-height: 1.5;">
                &ldquo;{esc(f.get('transcript_evidence'))}&rdquo;
              </div>

              <!-- Risk Profile Comparison -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin: 10px 0; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 12px;">
                <tr>
                  <td style="padding: 8px 12px; width: 50%; border-right: 1px solid #e2e8f0;">
                    <span style="color: #64748b; text-transform: uppercase; font-size: 10px; font-weight: 600;">Customer Risk Profile</span><br>
                    <strong style="color: #0f172a; font-size: 13px;">{esc(f.get('customer_risk_profile'))}</strong>
                  </td>
                  <td style="padding: 8px 12px; width: 50%;">
                    <span style="color: #64748b; text-transform: uppercase; font-size: 10px; font-weight: 600;">Product Risk Classification</span><br>
                    <strong style="color: #0f172a; font-size: 13px;">{esc(f.get('product_risk_class'))}</strong>
                  </td>
                </tr>
              </table>

              <!-- Regulatory Citation -->
              <div style="margin-top: 10px; padding: 10px 12px; background-color: #eff6ff; border: 1px solid #dbeafe; border-radius: 4px; font-size: 12px; color: #1e3a8a;">
                <strong>Regulatory Reference:</strong> {esc(f.get('regulation_citation_label'))} &middot; {esc(f.get('regulation_document_name'))} {source_link}
                {f'<div style="margin-top: 6px; font-size: 11px; color: #3b82f6; font-style: italic;">{esc(f.get("regulation_clause_text"))}</div>' if f.get("regulation_clause_text") else ''}
              </div>

              <!-- Reasoning & Recommended Action -->
              <div style="margin-top: 10px; font-size: 12px; color: #334155; line-height: 1.5;">
                <p style="margin: 4px 0;"><strong>Agentic Findings Analysis:</strong> {esc(f.get('reasoning'))}</p>
                <p style="margin: 4px 0; color: #b91c1c;"><strong>Mandated Action:</strong> {esc(f.get('recommended_action'))}</p>
              </div>
            </div>
            """
    else:
        findings_cards_html = f"""
        <div style="padding: 24px; text-align: center; background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; color: #64748b; font-size: 13px;">
          <strong>Surveillance Clear:</strong> No confirmed compliance findings identified for Relationship Manager {rm_name}.
        </div>
        """

    # Build Cases Summary Table HTML
    case_rows_html = ""
    if cases:
        for cs in cases:
            c_sev = get_severity_colors(cs.get("severity", "LOW"))
            is_resolved = cs.get("status") == "RESOLVED"
            st_bg = "#f0fdf4" if is_resolved else "#fffbeb"
            st_text = "#166534" if is_resolved else "#92400e"

            case_rows_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="padding: 8px 12px; font-family: monospace; font-size: 12px; font-weight: bold; color: #0f172a;">{esc(cs.get('case_id'))}</td>
              <td style="padding: 8px 12px; font-size: 12px; color: #334155;">{esc(cs.get('category'))}</td>
              <td style="padding: 8px 12px;">
                <span style="display: inline-block; padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 3px; background-color: {c_sev['pill_bg']}; color: #ffffff;">
                  {esc(cs.get('severity'))}
                </span>
              </td>
              <td style="padding: 8px 12px;">
                <span style="display: inline-block; padding: 2px 6px; font-size: 10px; font-weight: bold; font-family: monospace; border-radius: 3px; background-color: {st_bg}; color: {st_text};">
                  {esc(cs.get('status'))}
                </span>
              </td>
              <td style="padding: 8px 12px; font-size: 12px; color: #475569;">{esc(cs.get('assigned_reviewer_name'))}</td>
              <td style="padding: 8px 12px; font-size: 11px; color: #64748b; text-align: right;">{esc(cs.get('resolution_type') or 'Pending Action')}</td>
            </tr>
            """
    else:
        case_rows_html = """
        <tr>
          <td colspan="6" style="padding: 16px; text-align: center; color: #64748b; font-size: 12px;">
            No formal compliance cases logged.
          </td>
        </tr>
        """

    app_button_html = ""
    if app_url:
        app_button_html = f"""
        <div style="margin-top: 20px; text-align: center;">
          <a href="{esc(app_url)}/rm-analytics/{rm_id}" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: #0f172a; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; border-radius: 6px; letter-spacing: 0.3px;">
            Open RM Dossier in Vigil Intelligence &rarr;
          </a>
        </div>
        """

    # Assemble HTML email document
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vigil Compliance Report — {rm_name} ({rm_id})</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", Arial, sans-serif;
      color: #0f172a;
      -webkit-font-smoothing: antialiased;
    }}
    table {{ border-collapse: collapse; }}
    @media only screen and (max-width: 600px) {{
      .email-container {{ width: 100% !important; padding: 10px !important; }}
      .metric-col {{ display: block !important; width: 100% !important; margin-bottom: 8px !important; }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 24px 0; background-color: #f1f5f9;">

  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
      <td align="center">
        <!-- Main Wrapper Container -->
        <table class="email-container" width="680" cellpadding="0" cellspacing="0" style="max-width: 680px; width: 100%; background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color: #0f172a; padding: 24px 28px; color: #ffffff;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #94a3b8;">
                      VIGIL &middot; COMPLIANCE SURVEILLANCE
                    </div>
                    <h1 style="margin: 4px 0 0 0; font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                      RM STATUTORY COMPLIANCE REPORT
                    </h1>
                  </td>
                  <td align="right" style="vertical-align: top;">
                    <span style="display: inline-block; padding: 4px 10px; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px; font-size: 11px; font-family: monospace; color: #e2e8f0;">
                      {report_id}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- RM Profile Identity Card -->
          <tr>
            <td style="padding: 20px 28px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="70%" style="vertical-align: top;">
                    <div style="font-size: 18px; font-weight: 700; color: #0f172a;">
                      {rm_name}
                      <span style="font-size: 12px; font-family: monospace; padding: 2px 6px; background-color: #e2e8f0; border-radius: 3px; color: #334155; margin-left: 6px;">
                        {rm_id}
                      </span>
                    </div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 4px; line-height: 1.5;">
                      <strong>Branch:</strong> {branch} ({region}) &middot; 
                      <strong>Manager:</strong> {manager_name}
                      {f'<br><strong>Email:</strong> {rm_email}' if rm_email else ''}
                    </div>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                      Surveillance Period: <strong>{esc(metrics.get('reporting_period'))}</strong> &middot; Generated: {generated_at}
                    </div>
                  </td>
                  <td width="30%" align="right" style="vertical-align: top;">
                    <div style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: #64748b; letter-spacing: 0.5px;">
                      Composite Risk Score
                    </div>
                    <div style="font-size: 26px; font-weight: 800; font-family: monospace; color: {risk_color}; margin-top: 2px;">
                      {risk_score}<span style="font-size: 14px; color: #94a3b8; font-weight: normal;">/100</span>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Compliance Status Banner -->
          <tr>
            <td style="padding: 16px 28px;">
              <div style="padding: 14px 18px; background-color: {status_bg}; border: 1px solid {status_border}; border-radius: 6px;">
                <div style="font-size: 14px; font-weight: 700; color: {status_title_color};">
                  <span style="margin-right: 6px; font-size: 16px;">{status_icon}</span>
                  {status_headline}
                </div>
                <div style="font-size: 12px; color: #334155; margin-top: 4px; line-height: 1.4;">
                  {status_summary}
                </div>
              </div>
            </td>
          </tr>

          <!-- Executive Metrics Grid -->
          <tr>
            <td style="padding: 0 28px 20px 28px;">
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin-bottom: 10px;">
                Executive Surveillance Telemetry
              </div>
              <table width="100%" cellpadding="0" cellspacing="0" style="table-layout: fixed;">
                <tr>
                  <td class="metric-col" style="padding: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">Monitored Calls</div>
                    <div style="font-size: 22px; font-weight: 800; font-family: monospace; color: #0f172a; margin-top: 2px;">
                      {metrics.get('total_calls', 0)}
                    </div>
                  </td>
                  <td style="width: 10px;"></td>
                  <td class="metric-col" style="padding: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">Clean Calls</div>
                    <div style="font-size: 22px; font-weight: 800; font-family: monospace; color: #166534; margin-top: 2px;">
                      {metrics.get('clean_calls', 0)}
                    </div>
                  </td>
                  <td style="width: 10px;"></td>
                  <td class="metric-col" style="padding: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">With Findings</div>
                    <div style="font-size: 22px; font-weight: 800; font-family: monospace; color: #b91c1c; margin-top: 2px;">
                      {metrics.get('calls_with_findings', 0)}
                    </div>
                  </td>
                  <td style="width: 10px;"></td>
                  <td class="metric-col" style="padding: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">Open Cases</div>
                    <div style="font-size: 22px; font-weight: 800; font-family: monospace; color: #d97706; margin-top: 2px;">
                      {metrics.get('open_cases', 0)}
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Severity Breakdown Bar -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 10px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; font-size: 12px;">
                <tr>
                  <td style="color: #475569;">
                    <strong>Infractions Severity Profile:</strong>
                  </td>
                  <td align="right">
                    <span style="display: inline-block; margin-left: 12px; font-weight: 600; color: #b91c1c;">
                      HIGH: {metrics.get('high_severity_count', 0)}
                    </span>
                    <span style="display: inline-block; margin-left: 12px; font-weight: 600; color: #d97706;">
                      MEDIUM: {metrics.get('medium_severity_count', 0)}
                    </span>
                    <span style="display: inline-block; margin-left: 12px; font-weight: 600; color: #2563eb;">
                      LOW: {metrics.get('low_severity_count', 0)}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section: Monitored Calls Inventory -->
          <tr>
            <td style="padding: 10px 28px 24px 28px; border-top: 1px solid #e2e8f0;">
              <h2 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #0f172a; margin: 0 0 12px 0;">
                Monitored Advisory Calls ({len(calls)})
              </h2>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden;">
                <thead>
                  <tr style="background-color: #f8fafc; border-bottom: 2px solid #cbd5e1; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">
                    <th style="padding: 10px 12px; text-align: left;">Call ID</th>
                    <th style="padding: 10px 12px; text-align: left;">Customer</th>
                    <th style="padding: 10px 12px; text-align: left;">Date / Time</th>
                    <th style="padding: 10px 12px; text-align: left;">Language</th>
                    <th style="padding: 10px 12px; text-align: left;">Duration</th>
                    <th style="padding: 10px 12px; text-align: right;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {call_rows_html}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Section: Compliance Findings & Evidence Chain -->
          <tr>
            <td style="padding: 10px 28px 24px 28px; border-top: 1px solid #e2e8f0;">
              <h2 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #0f172a; margin: 0 0 12px 0;">
                Confirmed Compliance Infractions ({len(findings)})
              </h2>
              {findings_cards_html}
            </td>
          </tr>

          <!-- Section: Compliance Cases Summary -->
          {f'''
          <tr>
            <td style="padding: 10px 28px 24px 28px; border-top: 1px solid #e2e8f0;">
              <h2 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #0f172a; margin: 0 0 12px 0;">
                Compliance Case Workflow Summary ({len(cases)})
              </h2>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden;">
                <thead>
                  <tr style="background-color: #f8fafc; border-bottom: 2px solid #cbd5e1; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">
                    <th style="padding: 8px 12px; text-align: left;">Case ID</th>
                    <th style="padding: 8px 12px; text-align: left;">Category</th>
                    <th style="padding: 8px 12px; text-align: left;">Severity</th>
                    <th style="padding: 8px 12px; text-align: left;">Status</th>
                    <th style="padding: 8px 12px; text-align: left;">Assignee</th>
                    <th style="padding: 8px 12px; text-align: right;">Resolution</th>
                  </tr>
                </thead>
                <tbody>
                  {case_rows_html}
                </tbody>
              </table>
            </td>
          </tr>
          ''' if cases else ''}

          <!-- Footer & Audit Metadata -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 24px 28px; color: #64748b; font-size: 11px; line-height: 1.6;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <strong>VIGIL COMPLIANCE INTELLIGENCE SYSTEM</strong><br>
                    This statutory report was deterministically generated from indexed acoustic recordings, compliance cases, customer KYC profiles, and SEBI/AMFI regulatory circulars.
                    <br><br>
                    <em>Notice: This document contains confidential supervisory and client telemetry. Strictly intended for authorized internal compliance review.</em>
                  </td>
                </tr>
              </table>
              {app_button_html}
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
"""
    return html_content


def render_rm_report_text(report_data: Dict[str, Any]) -> str:
    """
    Render companion plain-text fallback report for email clients without HTML support.
    """
    rm = report_data.get("rm", {})
    metrics = report_data.get("metrics", {})
    status_eval = report_data.get("status_evaluation", {})
    calls = report_data.get("calls", [])
    findings = report_data.get("findings", [])
    report_id = report_data.get("report_id", "")
    generated_at = report_data.get("generated_at", "")

    lines = [
        "=" * 70,
        "VIGIL — AUTONOMOUS COMPLIANCE INTELLIGENCE",
        "RELATIONSHIP MANAGER COMPLIANCE REPORT",
        "=" * 70,
        f"RM: {rm.get('full_name')} ({rm.get('rm_id')})",
        f"Branch: {rm.get('branch')} ({rm.get('region')})",
        f"Reporting Period: {metrics.get('reporting_period')}",
        f"Report ID: {report_id}",
        f"Generated: {generated_at}",
        "",
        "-" * 70,
        f"COMPLIANCE EVALUATION: {status_eval.get('headline')}",
        "-" * 70,
        status_eval.get("summary", ""),
        "",
        "-" * 70,
        "EXECUTIVE SURVEILLANCE TELEMETRY",
        "-" * 70,
        f"Total Monitored Calls : {metrics.get('total_calls', 0)}",
        f"Clean Calls           : {metrics.get('clean_calls', 0)}",
        f"Calls With Findings   : {metrics.get('calls_with_findings', 0)}",
        f"Total Cases Logged    : {metrics.get('total_cases', 0)}",
        f"Open Cases            : {metrics.get('open_cases', 0)}",
        f"High Severity Count   : {metrics.get('high_severity_count', 0)}",
        f"Medium Severity Count : {metrics.get('medium_severity_count', 0)}",
        f"Low Severity Count    : {metrics.get('low_severity_count', 0)}",
        f"Composite Risk Score  : {metrics.get('risk_score', 0)}/100",
        "",
        "-" * 70,
        f"MONITORED CALLS ({len(calls)})",
        "-" * 70,
    ]

    for c in calls:
        lines.append(
            f"* {c.get('call_id')} | Cust: {c.get('customer_name')} | {c.get('date_time')} | "
            f"{c.get('duration_formatted')} | Status: {c.get('violation_status')}"
        )

    lines.extend([
        "",
        "-" * 70,
        f"CONFIRMED COMPLIANCE FINDINGS ({len(findings)})",
        "-" * 70,
    ])

    for f in findings:
        lines.extend([
            f"[{f.get('severity')}] {f.get('category')} (Confidence: {f.get('confidence_pct')}%)",
            f"  Call: {f.get('call_id')} | Timestamp: {f.get('timestamp_interval')}",
            f"  Evidence: \"{f.get('transcript_evidence')}\"",
            f"  Regulation: {f.get('regulation_citation_label')} — {f.get('regulation_document_name')}",
            f"  Reasoning: {f.get('reasoning')}",
            f"  Recommended Action: {f.get('recommended_action')}",
            "",
        ])

    lines.extend([
        "=" * 70,
        "Generated deterministically from Vigil Compliance Platform.",
        "Confidential — Internal BFSI compliance use only.",
        "=" * 70,
    ])

    return "\n".join(lines)
