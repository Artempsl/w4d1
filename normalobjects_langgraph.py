"""
NormalObjects - Strict Complaint Processor (LangGraph)
Lab 2: Structured, rule-based complaint processing using state machine workflow.

This system implements Bloyce's Protocol - a traceable, deterministic workflow
for processing complaints from the Downside Up universe.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import TypedDict, Optional, List, Dict, Tuple

from langgraph.graph import StateGraph, END

# ============================================================================
# LOGGING CONFIGURATION (Console + File)
# ============================================================================

# Configure logging to write to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('complaints.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

class ComplaintCategory(str, Enum):
    """Five valid complaint categories per Bloyce's Protocol."""
    PORTAL = "portal"
    MONSTER = "monster"
    PSYCHIC = "psychic"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"


class EffectivenessRating(str, Enum):
    """Resolution effectiveness ratings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplaintState(TypedDict):
    """
    State object that flows through the LangGraph workflow.
    
    This contains all information about a complaint as it progresses
    through intake → validate → investigate → resolve → close.
    """
    # Identity
    complaint_id: str
    complaint_text: str
    timestamp: datetime
    
    # Categorization
    category: Optional[ComplaintCategory]
    
    # Validation
    is_valid: bool
    validation_reason: str
    
    # Duplicate detection
    is_duplicate: bool
    linked_complaint_id: Optional[str]
    
    # Investigation
    investigation_evidence: str
    
    # Resolution
    resolution: str
    effectiveness_rating: Optional[EffectivenessRating]
    
    # Closure
    status: str  # "processing", "closed", "rejected", "escalated"
    customer_satisfied: Optional[bool]
    
    # Workflow tracing
    workflow_path: List[str]


# ============================================================================
# IN-MEMORY DUPLICATE DETECTION STORAGE
# ============================================================================

# Storage: {complaint_text_normalized: (complaint_id, timestamp)}
complaint_history: Dict[str, Tuple[str, datetime]] = {}

DUPLICATE_WINDOW_DAYS = 30


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize complaint text for duplicate detection.
    
    Args:
        text: Original complaint text
        
    Returns:
        Normalized text (lowercase, stripped, deduplicated whitespace)
    """
    return " ".join(text.lower().strip().split())


def create_initial_state(complaint_text: str) -> ComplaintState:
    """
    Create initial state for a new complaint.
    
    Args:
        complaint_text: The original complaint text
        
    Returns:
        ComplaintState with initial values
    """
    complaint_id = str(uuid.uuid4())[:8]  # Short ID for readability
    
    return ComplaintState(
        complaint_id=complaint_id,
        complaint_text=complaint_text,
        timestamp=datetime.now(),
        category=None,
        is_valid=False,
        validation_reason="",
        is_duplicate=False,
        linked_complaint_id=None,
        investigation_evidence="",
        resolution="",
        effectiveness_rating=None,
        status="processing",
        customer_satisfied=None,
        workflow_path=[]
    )


def check_duplicate(complaint_text: str) -> Tuple[bool, Optional[str]]:
    """
    Check if complaint is a duplicate within 30-day window.
    
    Args:
        complaint_text: The complaint text to check
        
    Returns:
        Tuple of (is_duplicate: bool, original_complaint_id: Optional[str])
    """
    normalized = normalize_text(complaint_text)
    current_time = datetime.now()
    
    if normalized in complaint_history:
        original_id, original_timestamp = complaint_history[normalized]
        
        # Check if within 30-day window
        time_diff = current_time - original_timestamp
        if time_diff <= timedelta(days=DUPLICATE_WINDOW_DAYS):
            logger.info(f"Duplicate detected! Links to complaint {original_id} from {time_diff.days} days ago")
            return True, original_id
        else:
            # Outside window - treat as new complaint
            logger.info(f"Similar complaint found but outside 30-day window ({time_diff.days} days)")
            complaint_history[normalized] = (str(uuid.uuid4())[:8], current_time)
            return False, None
    
    return False, None


def register_complaint(complaint_id: str, complaint_text: str) -> None:
    """
    Register a new complaint in duplicate detection storage.
    
    Args:
        complaint_id: Unique complaint identifier
        complaint_text: The complaint text
    """
    normalized = normalize_text(complaint_text)
    complaint_history[normalized] = (complaint_id, datetime.now())
    logger.debug(f"Registered complaint {complaint_id} in history")


# ============================================================================
# CATEGORIZATION KEYWORDS (Rule-Based)
# ============================================================================

CATEGORY_KEYWORDS = {
    ComplaintCategory.PORTAL: [
        "portal", "gate", "upside down", "dimension", "rift", "tear",
        "gateway", "opens", "timing anomaly", "location anomaly"
    ],
    ComplaintCategory.MONSTER: [
        "demogorgon", "creature", "monster", "beast", "entity",
        "attack", "behavior", "interact", "fight", "work together", "slug",
        "demo-dog"
    ],
    ComplaintCategory.PSYCHIC: [
        "psychic", "telekinesis", "telepathy", "eleven", "ability",
        "lift", "move things", "mental", "mind"
    ],
    ComplaintCategory.ENVIRONMENTAL: [
        "electricity", "power line", "light bulb", "flicker", "weather",
        "atmospheric", "temperature", "electromagnetic", "electrical",
        "voltage", "storm", "thunder"
    ]
}


# ============================================================================
# WORKFLOW NODES
# ============================================================================

def categorize_complaint(complaint_text: str) -> ComplaintCategory:
    """
    Categorize complaint using keyword matching with multi-word phrase priority.
    
    Args:
        complaint_text: The complaint text to categorize
        
    Returns:
        ComplaintCategory enum value
    """
    text_lower = complaint_text.lower()
    
    # Count matches for each category, prioritizing longer phrases
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                # Give higher weight to multi-word phrases
                word_count = len(keyword.split())
                score += word_count
        category_scores[category] = score
    
    # Get category with highest score
    max_score = max(category_scores.values())
    
    if max_score == 0:
        # No keywords matched - default to OTHER
        return ComplaintCategory.OTHER
    
    # Return category with highest score
    for category, score in category_scores.items():
        if score == max_score:
            return category
    
    return ComplaintCategory.OTHER


def intake_node(state: ComplaintState) -> ComplaintState:
    """
    First workflow node: Parse, categorize, and check for duplicates.
    
    This node:
    1. Checks for duplicate complaints (30-day window)
    2. Categorizes the complaint into one of 5 categories
    3. Registers the complaint in history
    4. Updates workflow path
    
    Args:
        state: Current complaint state
        
    Returns:
        Updated state with category and duplicate information
    """
    logger.info(f"[INTAKE] Processing complaint {state['complaint_id']}")
    logger.info(f"[INTAKE] Text: {state['complaint_text'][:80]}...")
    
    # Check for duplicates
    is_duplicate, linked_id = check_duplicate(state['complaint_text'])
    
    if is_duplicate:
        state['is_duplicate'] = True
        state['linked_complaint_id'] = linked_id
        state['status'] = "duplicate"
        logger.info(f"[INTAKE] ⚠️  Duplicate detected - linked to {linked_id}")
    else:
        # Register this complaint
        register_complaint(state['complaint_id'], state['complaint_text'])
    
    # Categorize the complaint
    category = categorize_complaint(state['complaint_text'])
    state['category'] = category
    
    logger.info(f"[INTAKE] ✓ Categorized as: {category.value}")
    
    # Update workflow path
    state['workflow_path'].append("intake")
    
    return state


def validate_portal_complaint(text: str) -> Tuple[bool, str]:
    """Validate portal complaints - must reference location or timing anomalies."""
    text_lower = text.lower()
    
    location_indicators = ["hawkins", "lab", "laboratory", "woods", "forest", 
                          "basement", "location", "place", "where", "at"]
    timing_indicators = ["time", "when", "hour", "minute", "day", "night", 
                        "morning", "evening", "random", "different", "unpredictable"]
    
    has_location = any(indicator in text_lower for indicator in location_indicators)
    has_timing = any(indicator in text_lower for indicator in timing_indicators)
    
    if has_location or has_timing:
        details = []
        if has_location:
            details.append("location reference")
        if has_timing:
            details.append("timing reference")
        return True, f"Valid portal complaint with {' and '.join(details)}"
    
    return False, "Portal complaint lacks specific location or timing information"


def validate_monster_complaint(text: str) -> Tuple[bool, str]:
    """Validate monster complaints - must describe creature behavior or interactions."""
    text_lower = text.lower()
    
    behavior_indicators = ["behavior", "act", "work", "fight", "attack", "move",
                          "interact", "react", "respond", "aggressive", "passive"]
    description_indicators = ["sometimes", "always", "never", "usually", "often",
                            "how", "when", "why", "together", "alone"]
    
    has_behavior = any(indicator in text_lower for indicator in behavior_indicators)
    has_description = any(indicator in text_lower for indicator in description_indicators)
    
    if has_behavior or has_description:
        return True, "Valid monster complaint with behavioral description"
    
    return False, "Monster complaint lacks creature behavior or interaction description"


def validate_psychic_complaint(text: str) -> Tuple[bool, str]:
    """Validate psychic complaints - must reference ability limitations or malfunctions."""
    text_lower = text.lower()
    
    ability_indicators = ["move", "lift", "telepathy", "telekinesis", "sense",
                         "feel", "see", "hear", "ability", "power"]
    limitation_indicators = ["can't", "cannot", "unable", "won't", "doesn't",
                           "limitation", "limit", "but", "however", "except",
                           "only", "just", "weak", "not"]
    
    has_ability = any(indicator in text_lower for indicator in ability_indicators)
    has_limitation = any(indicator in text_lower for indicator in limitation_indicators)
    
    # Require BOTH ability AND limitation for psychic complaints to be valid
    if has_ability and has_limitation:
        return True, "Valid psychic complaint with ability and limitation reference"
    elif has_ability:
        return False, "Psychic complaint mentions ability but lacks limitation details"
    
    return False, "Psychic complaint lacks specific ability or limitation details"


def validate_environmental_complaint(text: str) -> Tuple[bool, str]:
    """Validate environmental complaints - needs electricity, weather, or physical phenomena."""
    text_lower = text.lower()
    
    electrical_indicators = ["electricity", "power", "electrical", "electromagnetic",
                            "voltage", "current", "wire", "bulb", "light", "flicker"]
    weather_indicators = ["weather", "storm", "thunder", "lightning", "rain",
                         "temperature", "cold", "hot", "atmospheric"]
    physical_indicators = ["react", "strange", "unusual", "anomaly", "phenomenon",
                          "connection", "correlation", "when", "whenever"]
    
    has_electrical = any(indicator in text_lower for indicator in electrical_indicators)
    has_weather = any(indicator in text_lower for indicator in weather_indicators)
    has_physical = any(indicator in text_lower for indicator in physical_indicators)
    
    if has_electrical or has_weather:
        details = []
        if has_electrical:
            details.append("electrical")
        if has_weather:
            details.append("weather")
        if has_physical:
            details.append("physical phenomenon")
        return True, f"Valid environmental complaint with {', '.join(details)} reference"
    
    return False, "Environmental complaint lacks electricity, weather, or physical phenomenon details"


def validation_node(state: ComplaintState) -> ComplaintState:
    """
    Second workflow node: Validate complaint against category-specific rules.
    
    Validation rules per category:
    - PORTAL: Must reference location or timing anomalies
    - MONSTER: Must describe creature behavior or interactions
    - PSYCHIC: Must reference ability limitations or malfunctions
    - ENVIRONMENTAL: Must connect to electricity, weather, or physical phenomena
    - OTHER: Automatically escalated for manual review
    
    Args:
        state: Current complaint state
        
    Returns:
        Updated state with validation results
    """
    logger.info(f"[VALIDATE] Validating {state['category'].value} complaint {state['complaint_id']}")
    
    category = state['category']
    text = state['complaint_text']
    
    # Handle duplicates - skip validation, go straight to closure
    if state['is_duplicate']:
        state['is_valid'] = True
        state['validation_reason'] = "Duplicate complaint - linked to original, validation skipped"
        logger.info(f"[VALIDATE] ⚠️  Duplicate - skipping full validation")
        state['workflow_path'].append("validate")
        return state
    
    # Handle OTHER category - auto-escalate
    if category == ComplaintCategory.OTHER:
        state['is_valid'] = False
        state['validation_reason'] = "OTHER category - escalated for manual review"
        state['status'] = "escalated"
        logger.warning(f"[VALIDATE] ⚠️  OTHER category - escalating for manual review")
        state['workflow_path'].append("validate")
        return state
    
    # Category-specific validation
    validators = {
        ComplaintCategory.PORTAL: validate_portal_complaint,
        ComplaintCategory.MONSTER: validate_monster_complaint,
        ComplaintCategory.PSYCHIC: validate_psychic_complaint,
        ComplaintCategory.ENVIRONMENTAL: validate_environmental_complaint,
    }
    
    validator = validators.get(category)
    if validator:
        is_valid, reason = validator(text)
        state['is_valid'] = is_valid
        state['validation_reason'] = reason
        
        if is_valid:
            logger.info(f"[VALIDATE] ✓ Validation passed: {reason}")
        else:
            logger.warning(f"[VALIDATE] ✗ Validation failed: {reason}")
            state['status'] = "rejected"
    else:
        state['is_valid'] = False
        state['validation_reason'] = "No validator found for category"
        state['status'] = "rejected"
        logger.error(f"[VALIDATE] ✗ No validator for category {category}")
    
    # Update workflow path
    state['workflow_path'].append("validate")
    
    return state


def investigate_portal_complaint(text: str) -> str:
    """Generate investigation evidence for portal complaints."""
    evidence = [
        "INVESTIGATION REPORT - PORTAL ANOMALY",
        "=" * 50,
        "Temporal Pattern Analysis:",
        "  - Cross-referenced complaint timing with historical portal events",
        "  - Analyzed electromagnetic field readings at reported location",
        "  - Detected pattern consistent with dimensional instability",
        "",
        "Location Consistency Check:",
        "  - Verified spatial coordinates match known anomaly hotspots",
        "  - Confirmed environmental factors conducive to portal formation",
        "",
        "Environmental Factors:",
        "  - Elevated electromagnetic activity detected",
        "  - Atmospheric pressure anomalies recorded",
        "  - Correlation with nearby power grid fluctuations: POSITIVE",
        "",
        "CONCLUSION: Evidence supports dimensional portal activity"
    ]
    return "\n".join(evidence)


def investigate_monster_complaint(text: str) -> str:
    """Generate investigation evidence for monster complaints."""
    evidence = [
        "INVESTIGATION REPORT - CREATURE BEHAVIOR",
        "=" * 50,
        "Behavioral Data Collection:",
        "  - Reviewed historical creature interaction patterns",
        "  - Cross-referenced with known demogorgon behavioral models",
        "  - Identified pack behavior vs. solitary hunting patterns",
        "",
        "Interaction Pattern Analysis:",
        "  - Cooperative behavior observed during feeding cycles",
        "  - Territorial aggression noted in resource competition",
        "  - Social hierarchy indicators present",
        "",
        "Environmental Triggers:",
        "  - Creature activity correlates with portal stability",
        "  - Biological imperative drives behavioral variability",
        "  - Food scarcity influences cooperation vs. competition dynamics",
        "",
        "CONCLUSION: Behavioral patterns confirmed, documented for resolution"
    ]
    return "\n".join(evidence)


def investigate_psychic_complaint(text: str) -> str:
    """Generate investigation evidence for psychic complaints."""
    evidence = [
        "INVESTIGATION REPORT - PSYCHIC ABILITY ANALYSIS",
        "=" * 50,
        "Ability Specification Testing:",
        "  - Documented telekinetic force capacity measurements",
        "  - Tested maximum sustainable power output duration",
        "  - Recorded precision control at various distances",
        "",
        "Limitation Documentation:",
        "  - Mass threshold identified (heavy objects exceed capacity)",
        "  - Energy depletion rate calculated under sustained use",
        "  - Concentration requirements documented",
        "",
        "Contextual Factors:",
        "  - Emotional state impacts ability strength",
        "  - Physical exhaustion reduces effectiveness",
        "  - Environmental interference from electromagnetic sources",
        "",
        "CONCLUSION: Ability limitations within expected parameters for subject"
    ]
    return "\n".join(evidence)


def investigate_environmental_complaint(text: str) -> str:
    """Generate investigation evidence for environmental complaints."""
    evidence = [
        "INVESTIGATION REPORT - ENVIRONMENTAL ANOMALY",
        "=" * 50,
        "Power Line Activity Analysis:",
        "  - Monitored voltage fluctuations at reported location",
        "  - Detected unusual electromagnetic field patterns",
        "  - Correlated with known Upside Down proximity indicators",
        "",
        "Atmospheric Condition Assessment:",
        "  - Temperature variations outside normal range detected",
        "  - Barometric pressure instability recorded",
        "  - Air composition analysis shows trace exotic particles",
        "",
        "Anomaly Correlation Study:",
        "  - Electrical phenomena coincide with creature sightings: 87%",
        "  - Power grid disturbances align with portal activity: 92%",
        "  - Environmental readings consistent with dimensional bleed-through",
        "",
        "CONCLUSION: Environmental anomalies linked to Upside Down activity"
    ]
    return "\n".join(evidence)


def investigation_node(state: ComplaintState) -> ComplaintState:
    """
    Third workflow node: Investigate complaint and gather evidence.
    
    Investigation approach per category:
    - PORTAL: Temporal patterns, location consistency, environmental factors
    - MONSTER: Behavioral data, interaction patterns, triggers
    - PSYCHIC: Ability specs, limitations, contextual factors
    - ENVIRONMENTAL: Power line activity, atmospheric conditions, correlations
    
    Args:
        state: Current complaint state
        
    Returns:
        Updated state with investigation evidence
    """
    logger.info(f"[INVESTIGATE] Investigating {state['category'].value} complaint {state['complaint_id']}")
    
    # Investigation only proceeds if validation passed
    if not state['is_valid']:
        logger.warning(f"[INVESTIGATE] Skipped - complaint failed validation")
        state['investigation_evidence'] = "Investigation skipped - validation failed"
        state['workflow_path'].append("investigate")
        return state
    
    # Handle duplicates - reference original investigation
    if state['is_duplicate']:
        state['investigation_evidence'] = f"Duplicate - refer to original complaint {state['linked_complaint_id']} investigation"
        logger.info(f"[INVESTIGATE] Duplicate - referring to original {state['linked_complaint_id']}")
        state['workflow_path'].append("investigate")
        return state
    
    # Category-specific investigation
    investigators = {
        ComplaintCategory.PORTAL: investigate_portal_complaint,
        ComplaintCategory.MONSTER: investigate_monster_complaint,
        ComplaintCategory.PSYCHIC: investigate_psychic_complaint,
        ComplaintCategory.ENVIRONMENTAL: investigate_environmental_complaint,
    }
    
    investigator = investigators.get(state['category'])
    if investigator:
        evidence = investigator(state['complaint_text'])
        state['investigation_evidence'] = evidence
        logger.info(f"[INVESTIGATE] ✓ Evidence gathered ({len(evidence)} chars)")
        logger.debug(f"Evidence preview: {evidence[:100]}...")
    else:
        state['investigation_evidence'] = "No investigation template available"
        logger.warning(f"[INVESTIGATE] No investigator for category {state['category']}")
    
    # Update workflow path
    state['workflow_path'].append("investigate")
    
    return state


def resolve_portal_complaint() -> Tuple[str, EffectivenessRating]:
    """Generate resolution for portal complaints."""
    resolution = (
        "RESOLUTION - PORTAL TIMING PROTOCOL\n"
        "Per Downside Up Standard Procedure 4.2.1 (Portal Management):\n\n"
        "1. Install temporal monitoring equipment at reported location\n"
        "2. Establish 24-hour observation schedule using Protocol Delta-7\n"
        "3. Document portal opening patterns for predictive modeling\n"
        "4. Deploy electromagnetic stabilization field (Level 2)\n"
        "5. Provide complainant with portal detection device (Model PT-500)\n\n"
        "Expected outcome: 85% improvement in portal predictability within 14 days.\n"
        "Follow-up: Weekly monitoring reports required."
    )
    return resolution, EffectivenessRating.HIGH


def resolve_monster_complaint() -> Tuple[str, EffectivenessRating]:
    """Generate resolution for monster complaints."""
    resolution = (
        "RESOLUTION - CREATURE BEHAVIORAL MANAGEMENT\n"
        "Per Downside Up Standard Procedure 3.1.4 (Creature Containment):\n\n"
        "1. Deploy behavioral modification beacons at perimeter (Protocol CM-3)\n"
        "2. Establish food distribution schedule to reduce competition\n"
        "3. Install territorial boundary markers using pheromone attractants\n"
        "4. Implement creature tracking system for pattern analysis\n"
        "5. Escalate to Specialized Monster Response Team if aggression escalates\n\n"
        "Expected outcome: 70% reduction in unpredictable behavior within 21 days.\n"
        "Note: Creature behavior inherently variable - may require ongoing adjustment."
    )
    return resolution, EffectivenessRating.MEDIUM


def resolve_psychic_complaint() -> Tuple[str, EffectivenessRating]:
    """Generate resolution for psychic complaints."""
    resolution = (
        "RESOLUTION - PSYCHIC ABILITY OPTIMIZATION\n"
        "Per Downside Up Standard Procedure 5.3.2 (Psychic Development):\n\n"
        "1. Document current ability baseline and limitations\n"
        "2. Implement graduated training protocol (light → medium → heavy objects)\n"
        "3. Provide energy management techniques to extend duration\n"
        "4. Schedule regular rest intervals to prevent exhaustion\n"
        "5. Accept documented limitations as safety parameters\n\n"
        "Expected outcome: Improved control within existing capacity limits.\n"
        "Note: Mass limitations are biological - not system failures.\n"
        "Training may improve efficiency but not exceed natural thresholds."
    )
    return resolution, EffectivenessRating.MEDIUM


def resolve_environmental_complaint() -> Tuple[str, EffectivenessRating]:
    """Generate resolution for environmental complaints."""
    resolution = (
        "RESOLUTION - ENVIRONMENTAL ANOMALY MITIGATION\n"
        "Per Downside Up Standard Procedure 6.1.5 (Environmental Control):\n\n"
        "1. Install power grid stabilizers at affected locations\n"
        "2. Deploy atmospheric monitoring sensors (Model ENV-200)\n"
        "3. Establish electromagnetic shielding around sensitive equipment\n"
        "4. Coordinate with power company for surge protection upgrades\n"
        "5. ESCALATE to Environmental Specialist Team for sustained anomalies\n\n"
        "Expected outcome: 60% reduction in electrical fluctuations.\n"
        "Note: Complete elimination impossible while Upside Down proximity exists.\n"
        "Requires ongoing monitoring and potential specialist intervention."
    )
    return resolution, EffectivenessRating.LOW


def resolution_node(state: ComplaintState) -> ComplaintState:
    """
    Fourth workflow node: Apply resolution based on investigation findings.
    
    Resolution rules:
    - Must be specific to complaint category
    - Must reference established Downside Up procedures
    - Environmental/Monster may require specialist escalation
    - Must include predicted effectiveness rating (high/medium/low)
    - Cannot be applied without documented investigation
    
    Args:
        state: Current complaint state
        
    Returns:
        Updated state with resolution and effectiveness rating
    """
    logger.info(f"[RESOLVE] Applying resolution for {state['category'].value} complaint {state['complaint_id']}")
    
    # Skip resolution if not valid
    if not state['is_valid']:
        state['resolution'] = "Resolution not applied - complaint rejected"
        state['effectiveness_rating'] = None
        logger.warning(f"[RESOLVE] Skipped - complaint was rejected")
        state['workflow_path'].append("resolve")
        return state
    
    # Handle duplicates - reference original resolution
    if state['is_duplicate']:
        state['resolution'] = f"Duplicate - apply same resolution as complaint {state['linked_complaint_id']}"
        state['effectiveness_rating'] = EffectivenessRating.HIGH  # Following existing protocol
        logger.info(f"[RESOLVE] Duplicate - referring to original resolution")
        state['workflow_path'].append("resolve")
        return state
    
    # Verify investigation was completed
    if not state['investigation_evidence'] or "skipped" in state['investigation_evidence'].lower():
        state['resolution'] = "Resolution delayed - investigation incomplete"
        state['effectiveness_rating'] = None
        logger.error(f"[RESOLVE] Cannot resolve - investigation not completed")
        state['workflow_path'].append("resolve")
        return state
    
    # Category-specific resolution
    resolvers = {
        ComplaintCategory.PORTAL: resolve_portal_complaint,
        ComplaintCategory.MONSTER: resolve_monster_complaint,
        ComplaintCategory.PSYCHIC: resolve_psychic_complaint,
        ComplaintCategory.ENVIRONMENTAL: resolve_environmental_complaint,
    }
    
    resolver = resolvers.get(state['category'])
    if resolver:
        resolution, effectiveness = resolver()
        state['resolution'] = resolution
        state['effectiveness_rating'] = effectiveness
        logger.info(f"[RESOLVE] ✓ Resolution applied (effectiveness: {effectiveness.value})")
        
        # Log escalation warnings
        if "ESCALATE" in resolution:
            logger.warning(f"[RESOLVE] ⚠️  Escalation to specialist team required")
    else:
        state['resolution'] = "No resolution available for category"
        state['effectiveness_rating'] = None
        logger.error(f"[RESOLVE] No resolver for category {state['category']}")
    
    # Update workflow path
    state['workflow_path'].append("resolve")
    
    return state


def closure_node(state: ComplaintState) -> ComplaintState:
    """
    Fifth and final workflow node: Close complaint with confirmation.
    
    Closure requirements:
    - Confirm resolution was applied
    - Verify customer satisfaction (simulated)
    - Log: category, resolution, outcome, timestamp
    - Flag low effectiveness ratings for 30-day follow-up
    - Cannot skip workflow steps
    
    Args:
        state: Current complaint state
        
    Returns:
        Updated state with final closure information
    """
    logger.info(f"[CLOSE] Closing complaint {state['complaint_id']}")
    
    # Verify workflow integrity - must have gone through all steps
    required_steps = ["intake", "validate"]
    if state['is_valid'] and not state['is_duplicate']:
        required_steps.extend(["investigate", "resolve"])
    elif state['is_duplicate']:
        required_steps.extend(["investigate", "resolve"])
    
    for step in required_steps:
        if step not in state['workflow_path']:
            logger.error(f"[CLOSE] ✗ Cannot close - missing step: {step}")
            state['status'] = "error"
            state['workflow_path'].append("close")
            return state
    
    # Simulate customer satisfaction based on effectiveness rating
    if state['effectiveness_rating'] == EffectivenessRating.HIGH:
        state['customer_satisfied'] = True
        satisfaction_msg = "satisfied"
    elif state['effectiveness_rating'] == EffectivenessRating.MEDIUM:
        state['customer_satisfied'] = True  # Cautiously satisfied
        satisfaction_msg = "cautiously satisfied"
    elif state['effectiveness_rating'] == EffectivenessRating.LOW:
        state['customer_satisfied'] = False  # Requires follow-up
        satisfaction_msg = "requires follow-up"
    else:
        # Rejected or escalated complaints
        state['customer_satisfied'] = None
        satisfaction_msg = "N/A (complaint not resolved)"
    
    # Update final status
    if state['status'] == "rejected":
        final_status = "closed-rejected"
    elif state['status'] == "escalated":
        final_status = "closed-escalated"
    elif state['is_duplicate']:
        final_status = "closed-duplicate"
    else:
        final_status = "closed"
    
    state['status'] = final_status
    
    # Log closure details
    logger.info(f"[CLOSE] ✓ Complaint closed")
    logger.info(f"[CLOSE]   Category: {state['category'].value}")
    logger.info(f"[CLOSE]   Outcome: {final_status}")
    logger.info(f"[CLOSE]   Customer satisfaction: {satisfaction_msg}")
    logger.info(f"[CLOSE]   Timestamp: {state['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Flag for 30-day follow-up if needed
    if state['effectiveness_rating'] == EffectivenessRating.LOW:
        logger.warning(f"[CLOSE] ⚠️  Low effectiveness rating - 30-day follow-up required")
    
    # Update workflow path
    state['workflow_path'].append("close")
    
    logger.info(f"[CLOSE] Full workflow path: {' → '.join(state['workflow_path'])}")
    
    return state


# ============================================================================
# LANGGRAPH WORKFLOW ASSEMBLY
# ============================================================================

def should_continue_after_validation(state: ComplaintState) -> str:
    """
    Conditional edge: Determine next step after validation.
    
    Logic:
    - If invalid (rejected or escalated) → END
    - If valid → continue to investigation
    - If duplicate → continue to investigation (fast-track)
    
    Args:
        state: Current complaint state
        
    Returns:
        Next node name or END
    """
    if state['status'] in ['rejected', 'escalated']:
        logger.info(f"[ROUTER] Complaint {state['complaint_id']} ending: {state['status']}")
        return "end"
    else:
        logger.info(f"[ROUTER] Complaint {state['complaint_id']} continuing to investigation")
        return "investigate"


def build_complaint_workflow() -> StateGraph:
    """
    Build the complete LangGraph workflow for complaint processing.
    
    Workflow structure:
        START
          ↓
        intake (categorize, detect duplicates)
          ↓
        validate (category-specific rules)
          ↓
        [CONDITIONAL]
          ├─ invalid/escalated → END
          └─ valid → investigate
                        ↓
                     investigate (gather evidence)
                        ↓
                     resolve (apply solution)
                        ↓
                     close (confirm & log)
                        ↓
                      END
    
    Returns:
        Compiled StateGraph application
    """
    logger.info("[WORKFLOW] Building LangGraph complaint processing workflow")
    
    # Create the graph
    workflow = StateGraph(ComplaintState)
    
    # Add all nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("investigate", investigation_node)
    workflow.add_node("resolve", resolution_node)
    workflow.add_node("close", closure_node)
    
    # Set entry point
    workflow.set_entry_point("intake")
    
    # Define edges
    # Linear: intake → validate
    workflow.add_edge("intake", "validate")
    
    # Conditional: validate → investigate OR END
    workflow.add_conditional_edges(
        "validate",
        should_continue_after_validation,
        {
            "investigate": "investigate",
            "end": END
        }
    )
    
    # Linear: investigate → resolve → close → END
    workflow.add_edge("investigate", "resolve")
    workflow.add_edge("resolve", "close")
    workflow.add_edge("close", END)
    
    # Compile the graph
    app = workflow.compile()
    
    logger.info("[WORKFLOW] ✓ Workflow compiled successfully")
    return app


# Build the workflow (will be used in Stage 8 testing)
complaint_workflow = None  # Will be initialized when needed


# ============================================================================
# END-TO-END TESTING & DEMONSTRATION
# ============================================================================

def print_complaint_summary(state: ComplaintState) -> None:
    """Print a formatted summary of a processed complaint."""
    print("\n" + "=" * 70)
    print(f"COMPLAINT SUMMARY: {state['complaint_id']}")
    print("=" * 70)
    print(f"Text: {state['complaint_text'][:80]}...")
    print(f"Category: {state['category'].value if state['category'] else 'N/A'}")
    print(f"Status: {state['status']}")
    print(f"Valid: {state['is_valid']}")
    
    if state['is_duplicate']:
        print(f"Duplicate: YES (linked to {state['linked_complaint_id']})")
    
    if state['validation_reason']:
        print(f"Validation: {state['validation_reason']}")
    
    if state['effectiveness_rating']:
        print(f"Resolution Effectiveness: {state['effectiveness_rating'].value}")
    
    if state['customer_satisfied'] is not None:
        satisfaction = "✓ Satisfied" if state['customer_satisfied'] else "✗ Requires Follow-up"
        print(f"Customer Satisfaction: {satisfaction}")
    
    print(f"\nWorkflow Path: {' → '.join(state['workflow_path'])}")
    print("=" * 70)


def run_end_to_end_tests() -> None:
    """
    Run comprehensive end-to-end tests as specified in lab requirements.
    
    Tests include:
    1. All 5 complaint categories from lab
    2. Valid and invalid complaints
    3. Duplicate detection
    4. Workflow path visualization
    """
    global complaint_workflow
    
    print("\n" + "=" * 70)
    print("NORMALOBJECTS LANGGRAPH - END-TO-END TESTING")
    print("=" * 70)
    print("Lab 2: Strict Complaint Processor (Bloyce's Protocol)")
    print("=" * 70)
    
    # Clear history and build workflow
    complaint_history.clear()
    complaint_workflow = build_complaint_workflow()
    
    # Test cases from lab requirements
    test_complaints = [
        "The Downside Up portal opens at different times each day. How do I predict when?",
        "Demogorgons sometimes work together and sometimes fight. What's their deal?",
        "El can move things with her mind but can't lift heavy rocks. Why?",
        "Why do creatures and power lines react so strangely together?",
        "This is not a valid complaint about something random"  # Should be rejected
    ]
    
    print("\n\n" + "▼" * 70)
    print("TEST 1: PROCESSING 5 COMPLAINT CATEGORIES")
    print("▼" * 70)
    
    results = []
    
    for i, complaint_text in enumerate(test_complaints, 1):
        print(f"\n\n{'━' * 70}")
        print(f"Processing Complaint #{i}")
        print(f"{'━' * 70}")
        logger.info(f"\n{'=' * 70}")
        logger.info(f"TEST COMPLAINT #{i}: {complaint_text[:60]}...")
        logger.info(f"{'=' * 70}")
        
        # Create initial state
        initial_state = create_initial_state(complaint_text)
        
        # Run through workflow
        final_state = None
        for state_update in complaint_workflow.stream(initial_state):
            final_state = list(state_update.values())[0]
        
        # Print summary
        print_complaint_summary(final_state)
        results.append(final_state)
    
    # Duplicate detection test
    print("\n\n" + "▼" * 70)
    print("TEST 2: DUPLICATE DETECTION (30-DAY WINDOW)")
    print("▼" * 70)
    
    duplicate_test = "Portal opens at random times in Hawkins Lab."
    
    print(f"\n\n{'━' * 70}")
    print(f"Processing FIRST complaint")
    print(f"{'━' * 70}")
    logger.info(f"\n{'=' * 70}")
    logger.info(f"DUPLICATE TEST - FIRST SUBMISSION")
    logger.info(f"{'=' * 70}")
    
    state1 = create_initial_state(duplicate_test)
    final_state1 = None
    for state_update in complaint_workflow.stream(state1):
        final_state1 = list(state_update.values())[0]
    
    print_complaint_summary(final_state1)
    
    print(f"\n\n{'━' * 70}")
    print(f"Processing DUPLICATE complaint (same text)")
    print(f"{'━' * 70}")
    logger.info(f"\n{'=' * 70}")
    logger.info(f"DUPLICATE TEST - SECOND SUBMISSION (SHOULD BE DETECTED)")
    logger.info(f"{'=' * 70}")
    
    state2 = create_initial_state(duplicate_test)
    final_state2 = None
    for state_update in complaint_workflow.stream(state2):
        final_state2 = list(state_update.values())[0]
    
    print_complaint_summary(final_state2)
    
    # Summary statistics
    print("\n\n" + "▼" * 70)
    print("TEST RESULTS SUMMARY")
    print("▼" * 70)
    
    categories = {}
    statuses = {}
    
    for state in results + [final_state1, final_state2]:
        cat = state['category'].value if state['category'] else 'unknown'
        categories[cat] = categories.get(cat, 0) + 1
        statuses[state['status']] = statuses.get(state['status'], 0) + 1
    
    print("\nComplaints by Category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\nComplaints by Status:")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")
    
    print("\nWorkflow Path Types:")
    print(f"  Full workflow (5 steps): {sum(1 for s in results if len(s['workflow_path']) == 5)}")
    print(f"  Early termination (2 steps): {sum(1 for s in results if len(s['workflow_path']) == 2)}")
    print(f"  Duplicate handling: 1 (fast-track)")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"\nTotal complaints processed: {len(results) + 2}")
    print(f"Logs written to: complaints.log")
    print("=" * 70)


# ============================================================================
# MAIN EXECUTION (To be implemented in Stage 8)
# ============================================================================

if __name__ == "__main__":
    logger.info("NormalObjects LangGraph System - Initialization")
    logger.info("=" * 60)
    
    # Stage 2 validation tests
    print("\n[STAGE 2 VALIDATION]")
    
    # Test 1: State initialization
    test_complaint = "Portal opens at random times"
    state = create_initial_state(test_complaint)
    print(f"✓ Created initial state with ID: {state['complaint_id']}")
    print(f"✓ Workflow path initialized: {state['workflow_path']}")
    
    # Test 2: Text normalization
    normalized = normalize_text("  The   Portal   OPENS   ")
    assert normalized == "the portal opens", "Normalization failed"
    print(f"✓ Text normalization working")
    
    # Test 3: Duplicate detection
    # Clear history first
    complaint_history.clear()
    is_dup1, _ = check_duplicate("First complaint")
    register_complaint("test-001", "First complaint")
    is_dup2, linked = check_duplicate("First complaint")
    assert not is_dup1, "False positive on first check"
    assert is_dup2, "Failed to detect duplicate"
    print(f"✓ Duplicate detection working (linked to: {linked})")
    
    print(f"\n✅ Stage 2 complete: State definitions and helper functions validated")
    
    # ========================================================================
    # STAGE 3 VALIDATION
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 3 VALIDATION - INTAKE NODE]")
    print("=" * 60)
    
    # Clear history for clean test
    complaint_history.clear()
    
    test_cases = [
        ("Portal opens at different times each day", ComplaintCategory.PORTAL),
        ("Demogorgons sometimes work together", ComplaintCategory.MONSTER),
        ("El can move things with her mind but can't lift rocks", ComplaintCategory.PSYCHIC),
        ("Power lines react strangely with creatures", ComplaintCategory.ENVIRONMENTAL),
        ("This is a random complaint about nothing specific", ComplaintCategory.OTHER),
    ]
    
    print("\n1. Testing categorization:")
    for text, expected_category in test_cases:
        state = create_initial_state(text)
        state = intake_node(state)
        
        assert state['category'] == expected_category, \
            f"Expected {expected_category}, got {state['category']}"
        assert "intake" in state['workflow_path'], "Workflow path not updated"
        print(f"   ✓ '{text[:50]}...' → {state['category'].value}")
    
    print("\n2. Testing duplicate detection:")
    # First complaint
    state1 = create_initial_state("Portal opens at random times in Hawkins Lab")
    state1 = intake_node(state1)
    print(f"   ✓ First complaint {state1['complaint_id']}: is_duplicate={state1['is_duplicate']}")
    assert not state1['is_duplicate'], "First complaint wrongly marked as duplicate"
    
    # Duplicate complaint
    state2 = create_initial_state("Portal opens at random times in Hawkins Lab")
    state2 = intake_node(state2)
    print(f"   ✓ Second complaint {state2['complaint_id']}: is_duplicate={state2['is_duplicate']}, linked={state2['linked_complaint_id']}")
    assert state2['is_duplicate'], "Duplicate not detected"
    assert state2['linked_complaint_id'] == state1['complaint_id'], "Wrong linkage"
    
    print("\n✅ Stage 3 complete: Intake node validated")
    print("=" * 60)
    
    # ========================================================================
    # STAGE 4 VALIDATION
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 4 VALIDATION - VALIDATION NODE]")
    print("=" * 60)
    
    # Clear history for clean test
    complaint_history.clear()
    
    validation_test_cases = [
        # Valid cases
        ("Portal opens at different times each day in Hawkins Lab", ComplaintCategory.PORTAL, True),
        ("Demogorgons sometimes work together and sometimes fight", ComplaintCategory.MONSTER, True),
        ("El can move things with her mind but can't lift heavy rocks", ComplaintCategory.PSYCHIC, True),
        ("Power lines flicker when creatures are nearby", ComplaintCategory.ENVIRONMENTAL, True),
        
        # Invalid cases (insufficient detail)
        ("There's a portal", ComplaintCategory.PORTAL, False),
        ("I saw a monster", ComplaintCategory.MONSTER, False),
        ("Psychic powers exist", ComplaintCategory.PSYCHIC, False),
        
        # OTHER category (auto-escalate)
        ("This is about something completely random", ComplaintCategory.OTHER, False),
    ]
    
    print("\n1. Testing validation rules:")
    for text, expected_category, should_be_valid in validation_test_cases:
        state = create_initial_state(text)
        state = intake_node(state)
        state = validation_node(state)
        
        assert state['category'] == expected_category, \
            f"Wrong category: expected {expected_category}, got {state['category']}"
        
        if expected_category != ComplaintCategory.OTHER:
            assert state['is_valid'] == should_be_valid, \
                f"Validation mismatch for '{text}': expected {should_be_valid}, got {state['is_valid']}"
        
        status_icon = "✓" if state['is_valid'] else "✗"
        print(f"   {status_icon} [{state['category'].value}] {text[:50]}...")
        print(f"      → {state['validation_reason']}")
    
    print("\n2. Testing OTHER category escalation:")
    state = create_initial_state("Random complaint about coffee")
    state = intake_node(state)
    state = validation_node(state)
    assert state['status'] == "escalated", "OTHER category should be escalated"
    print(f"   ✓ OTHER category auto-escalated: {state['validation_reason']}")
    
    print("\n3. Testing duplicate handling:")
    state1 = create_initial_state("Portal timing is weird in the lab")
    state1 = intake_node(state1)
    state1 = validation_node(state1)
    
    state2 = create_initial_state("Portal timing is weird in the lab")
    state2 = intake_node(state2)
    state2 = validation_node(state2)
    
    assert state2['is_duplicate'], "Should be detected as duplicate"
    assert state2['is_valid'], "Duplicates should be marked valid"
    print(f"   ✓ Duplicate marked valid, validation skipped")
    
    assert "intake" in state1['workflow_path'], "Missing intake in path"
    assert "validate" in state1['workflow_path'], "Missing validate in path"
    print(f"   ✓ Workflow path tracking: {' → '.join(state1['workflow_path'])}")
    
    print("\n✅ Stage 4 complete: Validation node validated")
    print("=" * 60)
    
    # ========================================================================
    # STAGE 5 VALIDATION
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 5 VALIDATION - INVESTIGATION NODE]")
    print("=" * 60)
    
    # Clear history for clean test
    complaint_history.clear()
    
    investigation_test_cases = [
        ("Portal opens randomly in Hawkins Lab at midnight", ComplaintCategory.PORTAL),
        ("Demogorgons work together when hunting but fight over food", ComplaintCategory.MONSTER),
        ("El can move small objects but can't lift anything heavy", ComplaintCategory.PSYCHIC),
        ("Power lines flicker whenever creatures appear nearby", ComplaintCategory.ENVIRONMENTAL),
    ]
    
    print("\n1. Testing investigation evidence generation:")
    for text, expected_category in investigation_test_cases:
        state = create_initial_state(text)
        state = intake_node(state)
        state = validation_node(state)
        state = investigation_node(state)
        
        assert state['category'] == expected_category, f"Wrong category"
        assert state['is_valid'], f"Should be valid"
        assert state['investigation_evidence'], "Evidence should be generated"
        assert "INVESTIGATION REPORT" in state['investigation_evidence'], "Missing report header"
        assert "CONCLUSION" in state['investigation_evidence'], "Missing conclusion"
        
        print(f"   ✓ [{state['category'].value}] Evidence generated ({len(state['investigation_evidence'])} chars)")
        print(f"      First line: {state['investigation_evidence'].split(chr(10))[0]}")
    
    print("\n2. Testing investigation skipped for invalid complaints:")
    state = create_initial_state("There's a portal")  # Will fail validation
    state = intake_node(state)
    state = validation_node(state)
    state = investigation_node(state)
    
    assert not state['is_valid'], "Should be invalid"
    assert "skipped" in state['investigation_evidence'].lower(), "Should skip investigation"
    print(f"   ✓ Invalid complaint: investigation skipped")
    print(f"      Evidence: {state['investigation_evidence']}")
    
    print("\n3. Testing duplicate complaint investigation:")
    state1 = create_initial_state("Portal timing weird in the lab at night")
    state1 = intake_node(state1)
    state1 = validation_node(state1)
    state1 = investigation_node(state1)
    
    state2 = create_initial_state("Portal timing weird in the lab at night")
    state2 = intake_node(state2)
    state2 = validation_node(state2)
    state2 = investigation_node(state2)
    
    assert state2['is_duplicate'], "Should be duplicate"
    assert state1['complaint_id'] in state2['investigation_evidence'], "Should reference original"
    print(f"   ✓ Duplicate investigation refers to original: {state1['complaint_id']}")
    
    print("\n4. Testing workflow path:")
    state = create_initial_state("Storm activity correlates with electrical anomalies")
    state = intake_node(state)
    state = validation_node(state)
    state = investigation_node(state)
    
    expected_path = ["intake", "validate", "investigate"]
    assert state['workflow_path'] == expected_path, f"Wrong path: {state['workflow_path']}"
    print(f"   ✓ Workflow path correct: {' → '.join(state['workflow_path'])}")
    
    print("\n✅ Stage 5 complete: Investigation node validated")
    print("=" * 60)
    
    # ========================================================================
    # STAGE 6 VALIDATION
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 6 VALIDATION - RESOLUTION & CLOSURE NODES]")
    print("=" * 60)
    
    # Clear history for clean test
    complaint_history.clear()
    
    print("\n1. Testing resolution node with all categories:")
    
    resolution_test_cases = [
        ("Portal opens at different times in Hawkins Lab", ComplaintCategory.PORTAL, EffectivenessRating.HIGH),
        ("Demogorgons work together sometimes but fight over food", ComplaintCategory.MONSTER, EffectivenessRating.MEDIUM),
        ("El can move things but can't lift heavy objects", ComplaintCategory.PSYCHIC, EffectivenessRating.MEDIUM),
        ("Power lines flicker when creatures appear", ComplaintCategory.ENVIRONMENTAL, EffectivenessRating.LOW),
    ]
    
    for text, expected_category, expected_effectiveness in resolution_test_cases:
        state = create_initial_state(text)
        state = intake_node(state)
        state = validation_node(state)
        state = investigation_node(state)
        state = resolution_node(state)
        
        assert state['category'] == expected_category, f"Wrong category"
        assert state['resolution'], "Resolution should be generated"
        assert state['effectiveness_rating'] == expected_effectiveness, \
            f"Wrong effectiveness: expected {expected_effectiveness}, got {state['effectiveness_rating']}"
        assert "Downside Up Standard Procedure" in state['resolution'], "Missing procedure reference"
        
        print(f"   ✓ [{state['category'].value}] Resolution: {expected_effectiveness.value} effectiveness")
        print(f"      Procedure referenced: ✓")
    
    print("\n2. Testing closure node:")
    state = create_initial_state("Portal timing is unpredictable at Hawkins Lab")
    state = intake_node(state)
    state = validation_node(state)
    state = investigation_node(state)
    state = resolution_node(state)
    state = closure_node(state)
    
    assert state['status'] == "closed", f"Wrong status: {state['status']}"
    assert state['customer_satisfied'] is not None, "Customer satisfaction not set"
    assert "close" in state['workflow_path'], "Missing close in workflow path"
    
    print(f"   ✓ Complaint closed with status: {state['status']}")
    print(f"   ✓ Customer satisfied: {state['customer_satisfied']}")
    
    print("\n3. Testing full workflow path:")
    expected_full_path = ["intake", "validate", "investigate", "resolve", "close"]
    assert state['workflow_path'] == expected_full_path, \
        f"Wrong path: {state['workflow_path']}"
    print(f"   ✓ Complete workflow: {' → '.join(state['workflow_path'])}")
    
    print("\n4. Testing rejected complaint handling:")
    state = create_initial_state("There's a portal")  # Will fail validation
    state = intake_node(state)
    state = validation_node(state)
    state = investigation_node(state)
    state = resolution_node(state)
    state = closure_node(state)
    
    assert state['status'] == "closed-rejected", "Should be closed-rejected"
    assert state['customer_satisfied'] is None, "Rejected complaints have no satisfaction"
    print(f"   ✓ Rejected complaint closed properly: {state['status']}")
    
    print("\n5. Testing escalated complaint (OTHER category):")
    state = create_initial_state("Random complaint about coffee")
    state = intake_node(state)
    state = validation_node(state)
    # OTHER category gets escalated in validation
    assert state['status'] == "escalated", "Should be escalated"
    print(f"   ✓ OTHER category escalated: {state['status']}")
    
    print("\n6. Testing duplicate complaint workflow:")
    state1 = create_initial_state("Portal behavior is strange in the lab")
    state1 = intake_node(state1)
    state1 = validation_node(state1)
    state1 = investigation_node(state1)
    state1 = resolution_node(state1)
    state1 = closure_node(state1)
    
    state2 = create_initial_state("Portal behavior is strange in the lab")
    state2 = intake_node(state2)
    state2 = validation_node(state2)
    state2 = investigation_node(state2)
    state2 = resolution_node(state2)
    state2 = closure_node(state2)
    
    assert state2['is_duplicate'], "Should be duplicate"
    assert state2['status'] == "closed-duplicate", f"Wrong status: {state2['status']}"
    assert state1['complaint_id'] in state2['resolution'], "Should reference original"
    print(f"   ✓ Duplicate handled correctly: {state2['status']}")
    print(f"   ✓ References original complaint: {state1['complaint_id']}")
    
    print("\n7. Testing customer satisfaction levels:")
    # HIGH effectiveness
    state_high = create_initial_state("Portal opens randomly at different times")
    state_high = intake_node(state_high)
    state_high = validation_node(state_high)
    state_high = investigation_node(state_high)
    state_high = resolution_node(state_high)
    state_high = closure_node(state_high)
    assert state_high['customer_satisfied'] == True, "HIGH should be satisfied"
    print(f"   ✓ HIGH effectiveness → customer satisfied: {state_high['customer_satisfied']}")
    
    # LOW effectiveness (requires follow-up)
    state_low = create_initial_state("Electrical problems near power lines")
    state_low = intake_node(state_low)
    state_low = validation_node(state_low)
    state_low = investigation_node(state_low)
    state_low = resolution_node(state_low)
    state_low = closure_node(state_low)
    assert state_low['customer_satisfied'] == False, "LOW should need follow-up"
    print(f"   ✓ LOW effectiveness → requires follow-up: not satisfied")
    
    print("\n✅ Stage 6 complete: Resolution & Closure nodes validated")
    print("=" * 60)
    
    # ========================================================================
    # STAGE 7 VALIDATION
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 7 VALIDATION - LANGGRAPH WORKFLOW ASSEMBLY]")
    print("=" * 60)
    
    # Clear history for clean test
    complaint_history.clear()
    
    print("\n1. Building LangGraph workflow:")
    workflow_app = build_complaint_workflow()
    print(f"   ✓ Workflow compiled successfully")
    print(f"   ✓ Nodes: intake, validate, investigate, resolve, close")
    print(f"   ✓ Edges: linear + conditional routing")
    
    print("\n2. Testing valid complaint through full workflow:")
    initial_state = create_initial_state("Portal opens at random times in Hawkins Lab")
    
    # Execute the workflow
    final_state = None
    for state in workflow_app.stream(initial_state):
        # Get the last state update
        final_state = list(state.values())[0]
    
    assert final_state is not None, "Workflow should return final state"
    assert final_state['status'] == "closed", f"Should be closed, got {final_state['status']}"
    assert final_state['category'] == ComplaintCategory.PORTAL, "Should be portal category"
    assert final_state['is_valid'] == True, "Should be valid"
    assert final_state['resolution'], "Should have resolution"
    
    expected_path = ["intake", "validate", "investigate", "resolve", "close"]
    assert final_state['workflow_path'] == expected_path, \
        f"Wrong path: {final_state['workflow_path']}"
    
    print(f"   ✓ Complaint {final_state['complaint_id']} processed successfully")
    print(f"   ✓ Category: {final_state['category'].value}")
    print(f"   ✓ Status: {final_state['status']}")
    print(f"   ✓ Full path: {' → '.join(final_state['workflow_path'])}")
    
    print("\n3. Testing invalid complaint (early termination):")
    initial_state_invalid = create_initial_state("There's a portal")
    
    final_state_invalid = None
    for state in workflow_app.stream(initial_state_invalid):
        final_state_invalid = list(state.values())[0]
    
    assert final_state_invalid['status'] == "rejected", "Should be rejected"
    assert final_state_invalid['is_valid'] == False, "Should be invalid"
    
    # Should terminate after validate
    expected_path_invalid = ["intake", "validate"]
    assert final_state_invalid['workflow_path'] == expected_path_invalid, \
        f"Should terminate early, got: {final_state_invalid['workflow_path']}"
    
    print(f"   ✓ Invalid complaint terminated correctly")
    print(f"   ✓ Status: {final_state_invalid['status']}")
    print(f"   ✓ Path (early termination): {' → '.join(final_state_invalid['workflow_path'])}")
    
    print("\n4. Testing OTHER category (escalation path):")
    initial_state_other = create_initial_state("Random complaint about coffee")
    
    final_state_other = None
    for state in workflow_app.stream(initial_state_other):
        final_state_other = list(state.values())[0]
    
    assert final_state_other['category'] == ComplaintCategory.OTHER, "Should be OTHER"
    assert final_state_other['status'] == "escalated", "Should be escalated"
    
    # Should terminate after validate for OTHER category
    expected_path_other = ["intake", "validate"]
    assert final_state_other['workflow_path'] == expected_path_other, \
        f"Should escalate and terminate, got: {final_state_other['workflow_path']}"
    
    print(f"   ✓ OTHER category escalated correctly")
    print(f"   ✓ Status: {final_state_other['status']}")
    print(f"   ✓ Path (escalation): {' → '.join(final_state_other['workflow_path'])}")
    
    print("\n5. Testing all complaint categories through workflow:")
    test_complaints = [
        ("Demogorgons work together sometimes but fight other times", ComplaintCategory.MONSTER),
        ("El can move objects but can't lift heavy things", ComplaintCategory.PSYCHIC),
        ("Power lines flicker when creatures appear", ComplaintCategory.ENVIRONMENTAL),
    ]
    
    for text, expected_category in test_complaints:
        initial = create_initial_state(text)
        final = None
        for state in workflow_app.stream(initial):
            final = list(state.values())[0]
        
        assert final['category'] == expected_category, f"Wrong category"
        assert final['status'] == "closed", f"Should be closed"
        assert len(final['workflow_path']) == 5, f"Should have full path"
        print(f"   ✓ [{final['category'].value}] Full workflow completed")
    
    print("\n6. Testing conditional routing:")
    print(f"   ✓ Valid complaints → full workflow (5 steps)")
    print(f"   ✓ Invalid complaints → early termination (2 steps)")
    print(f"   ✓ OTHER category → escalation path (2 steps)")
    print(f"   ✓ Conditional edge after validation working correctly")
    
    print("\n✅ Stage 7 complete: LangGraph workflow assembled and validated")
    print("=" * 60)
    
    # ========================================================================
    # STAGE 8 - END-TO-END TESTING
    # ========================================================================
    print("\n" + "=" * 60)
    print("[STAGE 8 - END-TO-END TESTING]")
    print("=" * 60)
    print("Running comprehensive tests with lab requirements...")
    print("=" * 60)
    
    # Run the comprehensive end-to-end tests
    run_end_to_end_tests()
    
    print("\n✅ Stage 8 complete: End-to-end testing successful")
    print("=" * 60)
