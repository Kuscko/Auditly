"""
Generate validation reports for engineers and ATO auditors.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import asdict

from ..validators import ValidationResult, ValidationStatus


def _write_html(path: Path | str, html: str) -> None:
    """Write HTML with UTF-8 encoding (no BOM)."""
    p = Path(path)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(html)


def _get_evidence_guidance() -> Dict[str, str]:
    """Get collection guidance for each evidence type."""
    return {
        "terraform-plan": "<strong>Terraform Plan:</strong> Run <code>terraform plan -out=plan.tfplan && terraform show -json plan.tfplan</code> to export your infrastructure configuration and changes.",
        "audit-log": "<strong>Audit Logs:</strong> For Azure: Use Azure Portal > Activity Log or <code>az monitor activity-log list</code>. For AWS: Access CloudTrail via AWS Console or <code>aws cloudtrail lookup-events</code>.",
        "iam-policy": "<strong>IAM Policies:</strong> For Azure: <code>az role assignment list</code> to export role assignments. For AWS: <code>aws iam get-user-policy</code> and <code>aws iam list-attached-user-policies</code>.",
        "encryption-config": "<strong>Encryption Config:</strong> Check storage account and Key Vault settings. For Azure: <code>az storage account show --query encryption</code>.",
        "mfa-config": "<strong>MFA Configuration:</strong> For Azure: <code>az rest --method get --url 'https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies'</code> or check Azure Entra ID Conditional Access policies.",
        "logging-config": "<strong>Logging Configuration:</strong> Enable logging on storage accounts, databases, and application services. Check diagnostic settings and retention policies.",
        "cloudtrail-config": "<strong>CloudTrail Configuration:</strong> For AWS, enable CloudTrail in AWS Console or use <code>aws cloudtrail describe-trails</code> to verify it's enabled.",
        "backup-policy": "<strong>Backup Policy:</strong> Verify automated backup configuration is enabled. Check storage/database backup settings and retention periods.",
        "security-assessment": "<strong>Security Assessment:</strong> Run Azure Security Center assessments or third-party security scanning tools.",
        "compliance-report": "<strong>Compliance Report:</strong> Export compliance reports from your compliance management system or security tools.",
    }


def generate_engineer_report(
    results: Dict[str, ValidationResult],
    evidence: Dict[str, Any],
    output_path: Path | str,
) -> None:
    """
    Generate an engineer-focused HTML report with failures and remediation steps.
    
    Args:
        results: Dictionary of control_id -> ValidationResult
        evidence: Evidence dict used in validation
        output_path: Path to write HTML report
    """
    p = Path(output_path)
    
    # Get guidance for evidence collection
    evidence_guidance = _get_evidence_guidance()
    
    # Categorize results
    passed = {cid: r for cid, r in results.items() if r.status == ValidationStatus.PASS}
    insufficient = {cid: r for cid, r in results.items() if r.status == ValidationStatus.INSUFFICIENT_EVIDENCE}
    failed = {cid: r for cid, r in results.items() if r.status == ValidationStatus.FAIL}
    remediation_rows = ""
    for cid in sorted(list(failed.keys()) + list(insufficient.keys())):
        result = results[cid]
        remediation = result.remediation or "See control requirements and evidence guidelines"
        metadata = result.metadata or {}
        required_any = metadata.get("required_any", [])
        required_all = metadata.get("required_all", [])
        missing = metadata.get("missing", [])
        options = metadata.get("options", [])
        
        # Build list of required evidence with guidance
        needed_evidence = []
        if required_all:
            needed_evidence.extend(required_all)
        if options:
            needed_evidence.extend(options)
        
        guidance_text = ""
        for ev_type in needed_evidence:
            guidance = evidence_guidance.get(ev_type, f"<strong>{ev_type}:</strong> Collect evidence for this requirement.")
            guidance_text += f"<div style='margin: 8px 0; padding: 8px; background: #f0f7ff; border-left: 3px solid #1976d2; border-radius: 2px;'>{guidance}</div>"
        
        requirement_text = ""
        if required_all:
            requirement_text += f"<strong>Required:</strong> All of {', '.join(required_all)}<br/>"
        if required_any:
            requirement_text += f"<strong>Options:</strong> At least one of {', '.join(required_any)}<br/>"
        if missing:
            requirement_text += f"<strong>Missing:</strong> {', '.join(missing)}<br/>"
        if options:
            requirement_text += f"<strong>Need one of:</strong> {', '.join(options)}<br/>"
        
        remediation_rows += f"""
        <tr>
            <td><strong>{cid}</strong></td>
            <td>{requirement_text}</td>
            <td><em>{remediation}</em><br/>{guidance_text}</td>
        </tr>
        """
    
    # Build evidence summary
    evidence_summary = "<ul>"
    for ev_type, ev_data in evidence.items():
        if isinstance(ev_data, dict):
            path = ev_data.get("path", "(inline)")
            evidence_summary += f"<li><strong>{ev_type}</strong>: {path}</li>"
        else:
            evidence_summary += f"<li><strong>{ev_type}</strong>: (value)</li>"
    evidence_summary += "</ul>"
    
    # Calculate stats
    total = len(results)
    pass_count = len(passed)
    insufficient_count = len(insufficient)
    fail_count = len(failed)
    pass_rate = (pass_count / total * 100) if total > 0 else 0
    
    # Determine status color
    if fail_count > 0:
        status_color = "#d32f2f"  # red
        status_text = "ACTION REQUIRED"
    elif insufficient_count > 0:
        status_color = "#0dcaf0"  # teal
        status_text = "EVIDENCE NEEDED"
    else:
        status_color = "#388e3c"  # green
        status_text = "COMPLIANT"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>RapidRMF Engineer Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #2c3e50;
            line-height: 1.6;
            padding: 40px 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .header {{
            background: linear-gradient(135deg, {status_color} 0%, {status_color}dd 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 36px;
            margin-bottom: 10px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .header p {{
            font-size: 16px;
            opacity: 0.95;
            margin: 5px 0;
        }}
        .header .status {{
            font-size: 20px;
            margin-top: 15px;
            font-weight: 600;
            background: rgba(0,0,0,0.2);
            display: inline-block;
            padding: 10px 20px;
            border-radius: 4px;
        }}
        .timestamp {{
            opacity: 0.85;
            font-size: 13px;
            margin-top: 10px;
        }}
        .content {{
            padding: 40px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px;
            border-radius: 8px;
            border-left: 5px solid {status_color};
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }}
        .summary-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}
        .summary-card .number {{
            font-size: 42px;
            font-weight: 700;
            color: {status_color};
            margin-bottom: 8px;
        }}
        .summary-card .label {{
            font-size: 13px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            font-size: 24px;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 3px solid {status_color};
            font-weight: 700;
        }}
        .section p {{
            color: #555;
            margin-bottom: 15px;
            font-size: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        table thead {{
            background: #2c3e50;
            color: white;
        }}
        table th {{
            padding: 16px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        table td {{
            padding: 14px 16px;
            border-bottom: 1px solid #e0e0e0;
            font-size: 14px;
        }}
        table tbody tr {{
            transition: background-color 0.2s;
        }}
        table tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        table tbody tr:nth-child(odd) {{
            background-color: #fafbfc;
        }}
        .evidence-list {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid {status_color};
            margin: 15px 0;
        }}
        .evidence-list ul {{
            list-style: none;
            padding: 0;
        }}
        .evidence-list li {{
            padding: 8px 0;
            color: #2c3e50;
            font-size: 14px;
        }}
        .evidence-list strong {{
            color: {status_color};
            font-weight: 600;
        }}
        .evidence-list code {{
            background: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            color: #d63384;
        }}
        .controls-list {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.8;
            color: #2c3e50;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
        }}
        .no-items {{
            text-align: center;
            padding: 30px;
            color: #999;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
    <div class="header">
        <h1>RapidRMF Compliance Validation Report</h1>
        <p>Engineer View - Remediation & Action Items</p>
        <div class="status">Status: <strong>{status_text}</strong></div>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div class="content">
    <div class="summary">
        <div class="summary-card">
            <div class="number">{pass_count}</div>
            <div class="label">Passed ({pass_rate:.0f}%)</div>
        </div>
        <div class="summary-card">
            <div class="number">{insufficient_count}</div>
            <div class="label">Need Evidence</div>
        </div>
        <div class="summary-card">
            <div class="number">{fail_count}</div>
            <div class="label">Failed</div>
        </div>
        <div class="summary-card">
            <div class="number">{total}</div>
            <div class="label">Total Controls</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Available Evidence</h2>
        <p>Evidence sources already collected or available in your environment:</p>
        <div class="evidence-list">
            {evidence_summary}
        </div>
    </div>
    
    <div class="section">
        <h2>Action Items ({fail_count + insufficient_count} controls)</h2>
        <p>Controls below are missing required evidence. Collect the indicated evidence types to satisfy control compliance criteria.</p>
        <table>
            <thead>
                <tr>
                    <th>Control ID</th>
                    <th>Requirements</th>
                    <th>How to Collect Evidence</th>
                </tr>
            </thead>
            <tbody>
                {remediation_rows if remediation_rows else '<tr><td colspan="3" class="no-items">No action items - all controls compliant!</td></tr>'}
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Compliant Controls ({pass_count})</h2>
        <p>The following {pass_count} controls have the required evidence and satisfy compliance criteria:</p>
        <div class="controls-list">
            {', '.join(sorted(passed.keys())) if passed else 'None'}
        </div>
    </div>
    </div>
    </div>
</body>
</html>
"""
    _write_html(p, html)


def generate_auditor_report(
    results: Dict[str, ValidationResult],
    evidence: Dict[str, Any],
    output_path: Path | str,
) -> None:
    """
    Generate an ATO auditor-focused HTML report with evidence traceability.
    
    Args:
        results: Dictionary of control_id -> ValidationResult
        evidence: Evidence dict used in validation
        output_path: Path to write HTML report
    """
    p = Path(output_path)
    
    # Build detailed control table with evidence
    control_rows = ""
    for cid in sorted(results.keys()):
        result = results[cid]
        status_class = result.status.value.lower().replace("_", "-")
        status_display = result.status.value.replace("_", " ").title()
        
        metadata = result.metadata or {}
        evidence_locations = metadata.get("evidence_locations", {})
        matched_any = metadata.get("matched_required_any", [])
        matched_all = metadata.get("matched_required_all", [])
        required_any = metadata.get("required_any", [])
        required_all = metadata.get("required_all", [])
        
        # Build evidence table
        evidence_html = ""
        if evidence_locations:
            evidence_html = "<table style='font-size: 11px; margin: 5px 0;'>"
            for ev_type, ev_info in evidence_locations.items():
                path = ev_info.get("path", "(inline)") if isinstance(ev_info, dict) else str(ev_info)
                evidence_html += f"<tr><td><code>{ev_type}</code></td><td>{path}</td></tr>"
            evidence_html += "</table>"
        
        # Build requirements status
        req_html = "<div style='font-size: 11px; margin: 5px 0;'>"
        if required_all:
            matched = ", ".join(matched_all) if matched_all else "MISSING"
            req_html += f"<p><strong>Required All:</strong> {', '.join(required_all)}<br/><em style='color: #666;'>Matched: {matched}</em></p>"
        if required_any:
            matched = ", ".join(matched_any) if matched_any else "NONE"
            req_html += f"<p><strong>Required Any:</strong> {', '.join(required_any)}<br/><em style='color: #666;'>Matched: {matched}</em></p>"
        req_html += "</div>"
        
        control_rows += f"""
        <tr>
            <td><strong>{cid}</strong></td>
            <td><span class="status-badge status-{status_class}">{status_display}</span></td>
            <td>{req_html}</td>
            <td style='font-size: 11px;'>{evidence_html}</td>
            <td style='color: #666; font-size: 11px;'>{result.message}</td>
        </tr>
        """
    
    # Build evidence inventory
    evidence_inventory = ""
    for ev_type, ev_data in evidence.items():
        if isinstance(ev_data, dict):
            details = "<br/>".join([f"<strong>{k}:</strong> {v}" for k, v in ev_data.items()])
        else:
            details = str(ev_data)[:200]
        evidence_inventory += f"""
        <div style='margin-bottom: 15px; padding: 10px; background: #f9f9f9; border-left: 3px solid #2196F3;'>
            <strong>{ev_type}</strong>
            <div style='font-size: 12px; color: #555; margin-top: 5px;'>{details}</div>
        </div>
        """
    
    # Calculate stats
    total = len(results)
    passed = sum(1 for r in results.values() if r.status == ValidationStatus.PASS)
    insufficient = sum(1 for r in results.values() if r.status == ValidationStatus.INSUFFICIENT_EVIDENCE)
    failed = sum(1 for r in results.values() if r.status == ValidationStatus.FAIL)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>RapidRMF ATO Auditor Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #2c3e50;
            line-height: 1.6;
            padding: 40px 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .header {{
            background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 36px;
            margin-bottom: 10px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .header p {{
            font-size: 16px;
            opacity: 0.95;
            margin: 5px 0;
        }}
        .timestamp {{
            opacity: 0.85;
            font-size: 13px;
            margin-top: 15px;
        }}
        .content {{
            padding: 40px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px;
            border-radius: 8px;
            border-left: 5px solid #1976d2;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}
        .stat-card .number {{
            font-size: 42px;
            font-weight: 700;
            color: #1976d2;
            margin-bottom: 8px;
        }}
        .stat-card .label {{
            font-size: 13px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            font-size: 24px;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 3px solid #1976d2;
            font-weight: 700;
        }}
        .section p {{
            color: #555;
            margin-bottom: 15px;
            font-size: 15px;
        }}
        .evidence-box {{
            background: linear-gradient(135deg, #f0f4ff 0%, #f8fbff 100%);
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #1976d2;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .evidence-box strong {{
            color: #1565c0;
            font-weight: 600;
            display: block;
            margin-bottom: 8px;
        }}
        .evidence-box div {{
            font-size: 13px;
            color: #555;
            line-height: 1.5;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 13px;
        }}
        table thead {{
            background: #2c3e50;
            color: white;
        }}
        table th {{
            padding: 16px;
            text-align: left;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            font-size: 12px;
        }}
        table td {{
            padding: 12px 16px;
            border-bottom: 1px solid #e0e0e0;
            vertical-align: top;
        }}
        table tbody tr {{
            transition: background-color 0.2s;
        }}
        table tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        table tbody tr:nth-child(odd) {{
            background-color: #fafbfc;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            color: white;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-badge.status-pass {{
            background-color: #388e3c;
        }}
        .status-badge.status-insufficient-evidence {{
            background-color: #0dcaf0;
        }}
        .status-badge.status-fail {{
            background-color: #d32f2f;
        }}
        code {{
            background: #e8eef7;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            color: #1565c0;
        }}
        .requirement-section {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            font-size: 12px;
            margin: 5px 0;
            line-height: 1.5;
        }}
        .requirement-section strong {{
            color: #2c3e50;
            font-weight: 600;
        }}
        .requirement-section em {{
            color: #888;
        }}
    </style>
</head>
<body>
    <div class="container">
    <div class="header">
        <h1>RapidRMF Compliance Validation Report</h1>
        <p>Authority to Operate (ATO) Auditor View</p>
        <p>Comprehensive evidence traceability and control compliance assessment</p>
        <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
    </div>
    
    <div class="content">
    <div class="stats">
        <div class="stat-card">
            <div class="number">{passed}</div>
            <div class="label">Compliant</div>
        </div>
        <div class="stat-card">
            <div class="number">{insufficient}</div>
            <div class="label">Insufficient Evidence</div>
        </div>
        <div class="stat-card">
            <div class="number">{failed}</div>
            <div class="label">Non-Compliant</div>
        </div>
        <div class="stat-card">
            <div class="number">{total}</div>
            <div class="label">Total Controls</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Evidence Inventory</h2>
        <p>All evidence sources used in this validation:</p>
        {evidence_inventory}
    </div>
    
    <div class="section">
        <h2>Control Validation Details</h2>
        <p>Detailed assessment of each control with evidence traceability:</p>
        <table>
            <thead>
                <tr>
                    <th style="width: 80px;">Control ID</th>
                    <th style="width: 120px;">Status</th>
                    <th style="width: 280px;">Requirements & Match</th>
                    <th style="width: 280px;">Evidence Locations</th>
                    <th>Assessment Notes</th>
                </tr>
            </thead>
            <tbody>
                {control_rows}
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Summary</h2>
        <p><strong>Compliance Rate:</strong> {passed}/{total} controls ({passed/total*100:.1f}%) meet requirements</p>
        <p><strong>Evidence Coverage:</strong> {len(evidence)} evidence sources collected</p>
        <p><strong>Assessment Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
        <p style="color: #666; font-size: 13px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
            This report is generated automatically by RapidRMF and includes comprehensive evidence traceability.
            All file paths and evidence types are documented for audit trail purposes.
        </p>
    </div>
    </div>
    </div>
</body>
</html>
"""
    _write_html(p, html)
