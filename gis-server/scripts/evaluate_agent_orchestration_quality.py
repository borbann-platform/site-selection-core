"""Run golden-set agent quality evaluation with optional LLM-as-judge scoring."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


GOLDEN_SET: list[dict[str, Any]] = [
    {
        "id": 1,
        "category": "Complex Multi-Criteria Search",
        "user_query": "หาคอนโด Low-rise มือสอง ย่านอารีย์หรือสะพานควาย งบไม่เกิน 6 ล้าน ขนาด 40 ตรม. ขึ้นไป ต้องเป็นห้องมุมหรือทิศเหนือเท่านั้น และนิติบุคคลต้องมีประวัติการจัดการดี (ไม่มีปัญหาที่จอดรถ) ขอสรุปเปรียบเทียบมา 3 โครงการที่ราคาต่อตารางเมตรคุ้มที่สุด",
        "evaluation_criteria": "1. คัดกรองเฉพาะคอนโด Low-rise และห้องขนาด >40 ตรม. 2. ระบุทิศหรือตำแหน่งห้องมุมได้ถูกต้อง 3. มีการคำนวณราคาต่อตารางเมตรประกอบการตัดสินใจ 4. มีการอ้างอิงรีวิวนิติบุคคลหรือที่จอดรถ",
    },
    {
        "id": 2,
        "category": "Complex Multi-Criteria Search",
        "user_query": "อยากได้บ้านเดี่ยวใกล้โรงเรียนเตรียมอุดมศึกษาพัฒนาการ (พัฒนาการ 58) ระยะขับรถไม่เกิน 15 นาทีในช่วงเช้า 7.00 น. งบ 12-15 ล้าน ขอหมู่บ้านที่มีระบบสายไฟลงดินและมีห้องนอนล่างสำหรับผู้สูงอายุ",
        "evaluation_criteria": "1. วิเคราะห์ระยะทางและเวลาเดินทางจริงในช่วง Peak hour 2. คัดเลือกโครงการที่มีระบบสายไฟลงดิน (Underground cables) 3. ยืนยันว่าบ้านมีห้องนอนชั้นล่าง 4. อยู่ในงบประมาณที่กำหนด",
    },
    {
        "id": 3,
        "category": "ROI & Investment Analysis",
        "user_query": "มีเงินเย็น 20 ล้าน อยากซื้อตึกแถวแถวบรรทัดทองหรือทรงวาด เพื่อทำ AirBnB ช่วยวิเคราะห์ว่าทำเลไหน Yield สูงกว่ากัน และถ้ากู้ Bank 50% ดอกเบี้ย 6% ต่อปี จุดคุ้มทุน (Break-even) จะอยู่ที่ปีที่เท่าไหร่?",
        "evaluation_criteria": "1. เปรียบเทียบศักยภาพการปล่อยเช่ารายวันของทั้งสองทำเล 2. มีการคำนวณ Financial Projection (Revenue - Expense) 3. คำนวณจุดคุ้มทุนโดยพิจารณาจากดอกเบี้ยเงินกู้ 4. ให้คำแนะนำเรื่องข้อกฎหมายการทำ AirBnB ในไทยเบื้องต้น",
    },
    {
        "id": 4,
        "category": "ROI & Investment Analysis",
        "user_query": "เปรียบเทียบการลงทุนคอนโดรอบ ม.เกษตร (บางเขน) กับ ม.ธรรมศาสตร์ (รังสิต) ในงบ 3 ล้าน โครงการไหนมี Occupancy Rate สูงกว่าในช่วง 2 ปีนี้ และตัวไหนมี Capital Gain โดดเด่นที่สุด พร้อมคำนวณกำไรสุทธิหลังหักภาษีที่ดินและค่าส่วนกลาง",
        "evaluation_criteria": "1. อ้างอิงข้อมูลสถิติ Occupancy Rate ของกลุ่ม Student Condo 2. เปรียบเทียบ Capital Gain ย้อนหลัง 3. คำนวณ Net Profit โดยหักค่าใช้จ่ายส่วนกลางและภาษีที่ดินตามเรทปัจจุบัน",
    },
    {
        "id": 5,
        "category": "Comparative Neighborhood Analysis",
        "user_query": "วิเคราะห์ความคุ้มค่าระหว่างคอนโดติด BTS สายสีเขียว (บางนา) กับ สายสีเหลือง (ศรีนครินทร์) งบ 4 ล้าน เน้นสภาพคล่องในการขายต่อใน 5 ปีข้างหน้า และศักยภาพการเติบโตของราคาประเมินที่ดินย่านไหนดีกว่ากัน?",
        "evaluation_criteria": "1. เปรียบเทียบ Connectivity ของรถไฟฟ้าทั้งสองสาย 2. วิเคราะห์ Demand ในการซื้อต่อ (Resale Liquidity) 3. อ้างอิงแนวโน้มราคาประเมินที่ดินจากกรมธนารักษ์หรือข้อมูลตลาด",
    },
    {
        "id": 6,
        "category": "Comparative Neighborhood Analysis",
        "user_query": "เปรียบเทียบย่าน 'ทองหล่อ' กับ 'หลังสวน' สำหรับครอบครัวที่มีเด็กเล็ก งบเช่า 150,000 บาท/เดือน เน้น Walkability ไปสวนสาธารณะ ความหนาแน่น และคุณภาพอากาศ (PM 2.5) คุณแนะนำโครงการไหนเป็นพิเศษไหม?",
        "evaluation_criteria": "1. วิเคราะห์ระยะเดินไปสวนเบญจกิติ/สวนลุมพินี 2. เปรียบเทียบความพลุกพล่าน (Commercial vs Residential feel) 3. ให้ข้อมูลสภาพแวดล้อมและคุณภาพอากาศ 4. แนะนำโครงการที่สอดคล้องกับงบเช่า",
    },
    {
        "id": 7,
        "category": "Lifestyle & Amenities Integration",
        "user_query": "หาคอนโด 3 ห้องนอน ใกล้สวนเบญจกิติภายใน 500 เมตร ที่เลี้ยงสุนัขพันธุ์ใหญ่ได้ และใกล้ร้านกาแฟที่มี Co-working space สะดวก ขอโครงการที่มีพื้นที่วิ่งเล่นให้สุนัขด้วย",
        "evaluation_criteria": "1. คัดเฉพาะโครงการที่ระบุว่าเป็น Pet-friendly (Large breed) 2. ตรวจสอบระยะทางจริงถึงสวนเบญจกิติ 3. ระบุชื่อร้านกาแฟหรือ Co-working ใกล้เคียง 4. เช็ค Facility ของโครงการสำหรับสัตว์เลี้ยง",
    },
    {
        "id": 8,
        "category": "Lifestyle & Amenities Integration",
        "user_query": "ทำงาน WFH และชอบทำอาหาร หาคอนโดใกล้ MRT สายสีน้ำเงิน งบ 7 ล้าน ต้องมีครัวปิดระบายอากาศดี และอยู่ใกล้ตลาดสดหรือ Gourmet Market ในระยะเดินไม่เกิน 300 เมตร",
        "evaluation_criteria": "1. วิเคราะห์ Floor Plan ว่าเป็นห้องครัวปิด (Closed Kitchen) 2. ตรวจสอบระยะเดินเท้าไปยัง Supermarket หรือตลาดจริง 3. แนะนำทำเลบนสายสีน้ำเงินที่ตอบโจทย์ไลฟ์สไตล์การกิน",
    },
    {
        "id": 9,
        "category": "Legal & Financial Logic (Edge Case)",
        "user_query": "จะซื้อบ้านมือสองที่เจ้าของเสียชีวิตแล้วและยังไม่ได้ตั้งผู้จัดการมรดก ขั้นตอนกฎหมายต้องทำอย่างไร และควรระบุเงื่อนไขในสัญญาจะซื้อจะขายอย่างไรเพื่อลดความเสี่ยงเงินมัดจำ?",
        "evaluation_criteria": "1. อธิบายขั้นตอนการตั้งผู้จัดการมรดกตามกฎหมายไทย 2. แนะนำการระบุ 'เงื่อนไขบังคับก่อน' ในสัญญา 3. เตือนเรื่องการวางมัดจำหรือการทำสัญญาประนีประนอม",
    },
    {
        "id": 10,
        "category": "Financial Planning",
        "user_query": "จะซื้อบ้าน 8 ล้าน เงินเดือน 80,000 ภาระผ่อนรถ 12,000 ช่วยคำนวณวงเงินกู้สูงสุด (DSR) และเปรียบเทียบดอกเบี้ยรวมระหว่างผ่อนปกติ 30 ปี กับการโปะเพิ่มปีละ 100,000 บาท",
        "evaluation_criteria": "1. คำนวณ DSR (Debt Service Ratio) ตามเกณฑ์ธนาคาร 2. ประเมินวงเงินกู้ที่น่าจะอนุมัติ 3. แสดงการเปรียบเทียบดอกเบี้ยประหยัดจากการโปะ (Effective Interest Rate)",
    },
]


@dataclass
class EvalConfig:
    base_url: str
    auth_token: str
    refresh_token: str
    output_path: Path
    judge_enabled: bool
    judge_model: str
    judge_api_key: str
    judge_base_url: str
    runtime_provider: str
    runtime_model: str
    runtime_api_key: str
    runtime_base_url: str
    case_timeout_seconds: float
    judge_timeout_seconds: float
    auth_email: str
    auth_password: str
    raw_event_excerpt_limit: int = 12
    auth_refresh_count: int = 0


def summarize_sse_events(
    events: list[dict[str, Any]], excerpt_limit: int = 12
) -> list[dict[str, Any]]:
    excerpt: list[dict[str, Any]] = []

    for event in events[:excerpt_limit]:
        event_type = event.get("event")
        data = event.get("data") or {}
        normalized: dict[str, Any] = {"event": event_type}

        if event_type == "thinking":
            normalized["thinking"] = data.get("thinking")
        elif event_type == "step":
            normalized["step_type"] = data.get("type")
            normalized["name"] = data.get("name")
            normalized["status"] = data.get("status")
            if isinstance(data.get("output"), str):
                normalized["output_preview"] = str(data.get("output"))[:240]
        elif event_type == "token":
            token = data.get("token")
            if isinstance(token, str):
                normalized["token_preview"] = token[:240]
        elif event_type == "error":
            normalized["error"] = data

        excerpt.append(normalized)

    return excerpt


def parse_sse_events(payload: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in payload.split("\n"):
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if not data or data == "[DONE]":
            continue
        try:
            events.append(json.loads(data))
        except json.JSONDecodeError:
            continue
    return events


async def run_agent_case(
    client: httpx.AsyncClient,
    cfg: EvalConfig,
    base_url: str,
    case: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.auth_token}",
    }
    body = {
        "messages": [
            {
                "role": "user",
                "content": str(case["user_query"]),
            }
        ],
        "runtime": {
            "provider": cfg.runtime_provider,
            "model": cfg.runtime_model,
            "api_key": cfg.runtime_api_key,
            "base_url": cfg.runtime_base_url,
        },
    }
    try:
        response = await client.post(
            f"{base_url}/api/v1/chat/agent",
            headers=headers,
            json=body,
            timeout=cfg.case_timeout_seconds,
        )
        if response.status_code == 401 and cfg.refresh_token:
            await refresh_access_token(client, cfg)
            headers["Authorization"] = f"Bearer {cfg.auth_token}"
            response = await client.post(
                f"{base_url}/api/v1/chat/agent",
                headers=headers,
                json=body,
                timeout=cfg.case_timeout_seconds,
            )
        response.raise_for_status()
    except Exception as exc:
        return {
            "id": case["id"],
            "category": case["category"],
            "query": case["user_query"],
            "criteria": case["evaluation_criteria"],
            "status_code": 0,
            "session_id": None,
            "event_count": 0,
            "tools_called": [],
            "has_tool_call": False,
            "clarification": "",
            "response": "",
            "error": str(exc),
        }

    events = parse_sse_events(response.text)
    final_text = ""
    tool_names: list[str] = []
    clarification_message = ""
    engine_metadata: dict[str, Any] | None = None
    for event in events:
        event_type = event.get("event")
        data = event.get("data") or {}
        if event_type == "token":
            token = data.get("token")
            if isinstance(token, str):
                final_text += token
        if event_type == "step" and data.get("type") == "tool_call":
            name = data.get("name")
            if isinstance(name, str):
                tool_names.append(name)
        if event_type == "step" and data.get("type") == "waiting_user":
            output = data.get("output")
            if isinstance(output, str):
                clarification_message = output
        if event_type == "step" and data.get("name") == "Task Decomposition DAG":
            output = data.get("output")
            if isinstance(output, str):
                try:
                    parsed_output = json.loads(output)
                except json.JSONDecodeError:
                    parsed_output = None
                if isinstance(parsed_output, dict):
                    if engine_metadata is None:
                        engine_metadata = parsed_output
                    maybe_engine = parsed_output.get("engine")
                    if isinstance(maybe_engine, dict):
                        engine_metadata = maybe_engine

    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["user_query"],
        "criteria": case["evaluation_criteria"],
        "status_code": response.status_code,
        "session_id": response.headers.get("X-Session-ID"),
        "event_count": len(events),
        "engine": engine_metadata,
        "tools_called": tool_names,
        "has_tool_call": len(tool_names) > 0,
        "clarification": clarification_message,
        "response": final_text.strip(),
        "raw_event_excerpt": summarize_sse_events(events, cfg.raw_event_excerpt_limit),
    }


async def run_judge(
    client: httpx.AsyncClient,
    cfg: EvalConfig,
    result: dict[str, Any],
) -> dict[str, Any]:
    if not cfg.judge_enabled:
        return {
            "score": None,
            "verdict": "not_enabled",
            "notes": "Judge disabled",
        }

    prompt = (
        "You are a strict evaluator for a Thai real-estate assistant. "
        "Score 0-10 and return JSON only with keys: score, verdict, notes, criteria_checks.\n\n"
        f"Query:\n{result['query']}\n\n"
        f"Criteria:\n{result['criteria']}\n\n"
        f"Assistant response:\n{result['response']}\n\n"
        f"Tools called:\n{result['tools_called']}\n"
    )

    judge_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.judge_api_key}",
    }
    judge_body = {
        "model": cfg.judge_model,
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    resp = await client.post(
        f"{cfg.judge_base_url.rstrip('/')}/chat/completions",
        headers=judge_headers,
        json=judge_body,
        timeout=cfg.judge_timeout_seconds,
    )
    resp.raise_for_status()

    payload = resp.json()
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {
        "score": None,
        "verdict": "parse_error",
        "notes": content,
    }


async def register_and_login(
    client: httpx.AsyncClient, cfg: EvalConfig
) -> tuple[str, str]:
    register_payload = {
        "email": cfg.auth_email,
        "password": cfg.auth_password,
        "confirm_password": cfg.auth_password,
        "first_name": "Agent",
        "last_name": "Eval",
    }
    register_resp = await client.post(
        f"{cfg.base_url}/api/v1/auth/register",
        json=register_payload,
        timeout=30.0,
    )
    if register_resp.status_code not in (200, 201, 400):
        register_resp.raise_for_status()

    login_resp = await client.post(
        f"{cfg.base_url}/api/v1/auth/login",
        data={"username": cfg.auth_email, "password": cfg.auth_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    login_resp.raise_for_status()
    payload = login_resp.json()
    return payload["access_token"], payload["refresh_token"]


async def refresh_access_token(client: httpx.AsyncClient, cfg: EvalConfig) -> None:
    if not cfg.refresh_token:
        return
    refresh_resp = await client.post(
        f"{cfg.base_url}/api/v1/auth/refresh",
        json={"refresh_token": cfg.refresh_token},
        timeout=30.0,
    )
    refresh_resp.raise_for_status()
    payload = refresh_resp.json()
    cfg.auth_token = payload["access_token"]
    cfg.refresh_token = payload.get("refresh_token", cfg.refresh_token)
    cfg.auth_refresh_count += 1


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agent orchestration quality")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.getenv("EVAL_AUTH_TOKEN", ""))
    parser.add_argument(
        "--output",
        default="gis-server/reports/agent_orchestration_quality.json",
    )
    parser.add_argument("--judge", action="store_true")
    parser.add_argument(
        "--judge-model", default=os.getenv("JUDGE_MODEL", "deepseek-chat")
    )
    parser.add_argument("--judge-api-key", default=os.getenv("JUDGE_API_KEY", ""))
    parser.add_argument(
        "--judge-base-url",
        default=os.getenv("JUDGE_BASE_URL", "https://api.deepseek.com/v1"),
    )
    parser.add_argument(
        "--runtime-provider",
        default=os.getenv("EVAL_RUNTIME_PROVIDER", "openai_compatible"),
    )
    parser.add_argument(
        "--runtime-model",
        default=os.getenv("EVAL_RUNTIME_MODEL", "deepseek-chat"),
    )
    parser.add_argument(
        "--runtime-api-key",
        default=os.getenv("EVAL_RUNTIME_API_KEY", ""),
    )
    parser.add_argument(
        "--runtime-base-url",
        default=os.getenv("EVAL_RUNTIME_BASE_URL", "https://api.deepseek.com/v1"),
    )
    parser.add_argument("--case-timeout", type=float, default=300.0)
    parser.add_argument("--judge-timeout", type=float, default=120.0)
    parser.add_argument("--raw-event-excerpt-limit", type=int, default=12)
    parser.add_argument("--auth-email", default=os.getenv("EVAL_AUTH_EMAIL", ""))
    parser.add_argument("--auth-password", default=os.getenv("EVAL_AUTH_PASSWORD", ""))
    args = parser.parse_args()

    auth_email = args.auth_email or f"agent.eval.{int(time.time())}@example.com"
    auth_password = args.auth_password or "Passw0rd123"

    runtime_api_key = args.runtime_api_key or args.judge_api_key
    if not runtime_api_key:
        raise SystemExit(
            "Missing runtime API key. Provide --runtime-api-key or EVAL_RUNTIME_API_KEY."
        )

    cfg = EvalConfig(
        base_url=args.base_url.rstrip("/"),
        auth_token=args.token,
        refresh_token="",
        output_path=Path(args.output),
        judge_enabled=bool(args.judge),
        judge_model=args.judge_model,
        judge_api_key=args.judge_api_key,
        judge_base_url=args.judge_base_url,
        runtime_provider=args.runtime_provider,
        runtime_model=args.runtime_model,
        runtime_api_key=runtime_api_key,
        runtime_base_url=args.runtime_base_url,
        case_timeout_seconds=args.case_timeout,
        judge_timeout_seconds=args.judge_timeout,
        auth_email=auth_email,
        auth_password=auth_password,
        raw_event_excerpt_limit=args.raw_event_excerpt_limit,
    )

    if cfg.judge_enabled and not cfg.judge_api_key:
        raise SystemExit("Judge enabled but missing judge API key.")

    cfg.output_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        if not cfg.auth_token:
            access_token, refresh_token = await register_and_login(client, cfg)
            cfg.auth_token = access_token
            cfg.refresh_token = refresh_token
        for case in GOLDEN_SET:
            case_result = await run_agent_case(
                client=client,
                cfg=cfg,
                base_url=cfg.base_url,
                case=case,
            )
            case_result["judge"] = await run_judge(client, cfg, case_result)
            results.append(case_result)

    report = {
        "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": cfg.base_url,
        "judge_enabled": cfg.judge_enabled,
        "auth": {
            "email": cfg.auth_email,
            "refresh_count": cfg.auth_refresh_count,
            "runtime_provider": cfg.runtime_provider,
            "runtime_model": cfg.runtime_model,
        },
        "cases": results,
    }

    cfg.output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote report: {cfg.output_path}")


if __name__ == "__main__":
    asyncio.run(main())
