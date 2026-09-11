from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from core.discovery_catalog import GOAL_KEYWORDS, iter_profiles
from core.provider_router import call_llm


logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return name.lower().strip()


def call_llm_mapping(use_case: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Use an Agentic approach to map use case to inventory and identify gaps.
    """
    prompt = f"""
    Role: Strategic Integration Architect Agent
    Task: Analyze the following automation goal and map it against the current system estate.
    
    Automation Goal:
    {use_case}
    
    Current System Inventory:
    {inventory}
    
    Chain of Thought:
    1. Identify 'Anchor Systems': Which existing systems in the inventory are required?
    2. Identify 'System Gaps': Which systems mentioned in the goal are MISSING from the inventory?
    3. Trace 'Data Flow': Define SOURCE -> DESTINATION, the ENTITY (e.g. Invoice), and the TRIGGER (e.g. Deal Closed).
    4. Assess 'Business Impact': How much manual work is saved? (Frequency x Criticality).
    5. Estimate 'Implementation Effort': Small, Medium, or Large?
    
    Output Format:
    Return a JSON object with:
    - "required_systems": ["SystemA", "SystemB"]
    - "data_flows": [
        {{"source": "SystemA", "destination": "SystemB", "entity_type": "...", "trigger": "..."}}
      ]
    - "gaps": [
        {{"system_name": "...", "status": "available/missing", "priority": "Low/Medium/High/Critical", "effort_estimate": "Small/Medium/Large", "details": "..."}}
      ]
    - "strategic_recommendation": "A short summary of the integration roadmap."
    """
    result = call_llm(prompt)
    return result if isinstance(result, dict) else {}


def _infer_required_systems(use_case: Dict[str, Any], inventory: List[Dict[str, Any]]) -> List[str]:
    explicit_targets = [name for name in use_case.get("target_systems", []) if name]
    if explicit_targets:
        return explicit_targets

    goal_text = " ".join(
        filter(
            None,
            [
                use_case.get("business_goal", ""),
                use_case.get("description", ""),
                use_case.get("title", ""),
            ],
        )
    ).lower()

    discovered: List[str] = []

    inventory_names = {item["name"] for item in inventory}
    for inventory_name in inventory_names:
        if inventory_name.lower() in goal_text:
            discovered.append(inventory_name)

    for keyword, systems in GOAL_KEYWORDS.items():
        if keyword in goal_text:
            discovered.extend(systems)

    for profile in iter_profiles():
        if any(alias in goal_text for alias in profile.aliases):
            discovered.append(profile.canonical_name)

    deduped: List[str] = []
    seen = set()
    for name in discovered:
        key = _normalize(name)
        if key not in seen:
            deduped.append(name)
            seen.add(key)
    return deduped


def _business_impact_label(score: int) -> str:
    if score >= 15:
        return "Critical"
    if score >= 8:
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"


def map_use_case_to_inventory(use_case: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare a use case's requirements against the discovered inventory.
    """
    # Try LLM first
    llm_map = call_llm_mapping(use_case, inventory)
    
    use_case_id = use_case.get("id", 0)
    use_case_title = use_case.get("title", "Unknown")
    frequency = use_case.get("frequency", "Monthly")
    criticality = use_case.get("criticality", "Medium")
    
    if llm_map:
        required_systems = llm_map.get("required_systems", [])
        gaps = llm_map.get("gaps", [])
        data_flows = llm_map.get("data_flows", [])
    else:
        data_flows = use_case.get("data_flows", [])
        required_systems = _infer_required_systems(use_case, inventory)
        gaps = [] # Will be populated below

    frequency_weights = {"Daily": 5, "Weekly": 3, "Monthly": 1}
    criticality_weights = {"High": 3, "Medium": 2, "Low": 1}

    freq_weight = frequency_weights.get(frequency, 1)
    uc_criticality_weight = criticality_weights.get(criticality, 2)

    inventory_map = {_normalize(system["name"]): system for system in inventory}

    gaps_to_return: List[Dict[str, Any]] = []
    dependencies: List[str] = []
    available_systems: List[str] = []
    missing_systems: List[str] = []
    graph_nodes: List[Dict[str, Any]] = [{"id": f"use_case:{use_case_id}", "label": use_case_title, "type": "use_case"}]
    graph_edges: List[Dict[str, Any]] = []
    missing_counter = Counter()

    # If LLM provided gaps, use them, otherwise build them
    if llm_map and llm_map.get("gaps"):
        for gap in llm_map["gaps"]:
            # Ensure required fields are present
            gap.setdefault("status", "missing")
            gap.setdefault("priority", "Medium")
            gap.setdefault("priority_score", 5 if gap["status"] == "missing" else 1)
            gap.setdefault("effort_estimate", "Large" if gap["status"] == "missing" else "None")
            gap.setdefault("dependencies", [])
            gaps_to_return.append(gap)
            
            normalized_name = _normalize(gap["system_name"])
            graph_nodes.append({"id": f"system:{normalized_name}", "label": gap["system_name"], "type": "system", "status": gap["status"]})
            graph_edges.append({"source": f"use_case:{use_case_id}", "target": f"system:{normalized_name}", "type": "requires"})
            
            if gap["status"] == "missing":
                missing_systems.append(gap["system_name"])
                dependency = f"Integration with {gap['system_name']} must exist before {use_case_title} can be automated."
                dependencies.append(dependency)
                gap["dependencies"].append(dependency)
                missing_counter[gap["priority"]] += 1
            else:
                available_systems.append(gap["system_name"])
    else:
        for system_name in required_systems:
            normalized_name = _normalize(system_name)
            system_info = inventory_map.get(normalized_name, {})
            is_missing = normalized_name not in inventory_map
            status = "missing" if is_missing else "available"
            system_criticality = system_info.get("criticality", criticality)
            crit_weight = criticality_weights.get(system_criticality, uc_criticality_weight)
            priority_score = crit_weight * freq_weight * (2 if is_missing else 1)
            priority = _business_impact_label(priority_score)

            gap_entry = {
                "system_name": system_name,
                "status": status,
                "priority": priority,
                "priority_score": priority_score,
                "effort_estimate": "Large" if is_missing else "None",
                "criticality": system_criticality,
                "details": (
                    f"Discovered with {system_info.get('confidence_score', 0.0) * 100:.1f}% confidence."
                    if not is_missing
                    else "No evidence found in the current inventory."
                ),
                "dependencies": [],
            }

            gaps_to_return.append(gap_entry)
            graph_nodes.append({"id": f"system:{normalized_name}", "label": system_name, "type": "system", "status": status})
            graph_edges.append({"source": f"use_case:{use_case_id}", "target": f"system:{normalized_name}", "type": "requires"})

            if is_missing:
                missing_systems.append(system_name)
                dependency = f"Integration with {system_name} must exist before {use_case_title} can be automated."
                dependencies.append(dependency)
                gap_entry["dependencies"].append(dependency)
                missing_counter[priority] += 1
            else:
                available_systems.append(system_name)

    traced_flows = []
    # Use LLM data flows if available
    if llm_map and llm_map.get("data_flows"):
        for flow in llm_map["data_flows"]:
            source = flow.get("source", "Unknown")
            destination = flow.get("destination", "Unknown")
            is_blocked = _normalize(source) not in inventory_map or _normalize(destination) not in inventory_map
            traced_flows.append(
                {
                    "source": source,
                    "destination": destination,
                    "entity_type": flow.get("entity_type", "Data"),
                    "trigger": flow.get("trigger", "Event"),
                    "is_blocked": is_blocked,
                }
            )
            graph_edges.append(
                {
                    "source": f"system:{_normalize(source)}",
                    "target": f"system:{_normalize(destination)}",
                    "type": "flow",
                    "blocked": is_blocked,
                }
            )
    else:
        for flow in data_flows:
            source = flow.get("source", "Unknown")
            destination = flow.get("destination", "Unknown")
            is_blocked = _normalize(source) not in inventory_map or _normalize(destination) not in inventory_map
            traced_flows.append(
                {
                    "source": source,
                    "destination": destination,
                    "entity_type": flow.get("entity_type", "Data"),
                    "trigger": flow.get("trigger", "Event"),
                    "is_blocked": is_blocked,
                }
            )
            graph_edges.append(
                {
                    "source": f"system:{_normalize(source)}",
                    "target": f"system:{_normalize(destination)}",
                    "type": "flow",
                    "blocked": is_blocked,
                }
            )

    report = {
        "use_case_id": use_case_id,
        "use_case_title": use_case_title,
        "business_goal": use_case.get("business_goal", use_case.get("description", use_case_title)),
        "frequency": frequency,
        "required_systems": required_systems,
        "available_systems": available_systems,
        "missing_systems": missing_systems,
        "integration_gaps": [gap for gap in gaps_to_return if gap["status"] == "missing"],
        "gaps": gaps_to_return,
        "data_flow_analysis": traced_flows,
        "dependency_mapping": dependencies,
        "dependency_graph": {"nodes": graph_nodes, "edges": graph_edges},
        "business_impact": _business_impact_label(sum(gap.get("priority_score", 0) for gap in gaps_to_return)),
        "priority_score": sum(gap.get("priority_score", 0) for gap in gaps_to_return),
        "downstream_blockers": dict(missing_counter),
        "strategic_recommendation": llm_map.get("strategic_recommendation", "Analyze inventory and implement missing connectors.") if llm_map else "Analyze inventory and implement missing connectors.",
    }

    logger.info("Generated gap report for use case %s", use_case_title)
    return report
