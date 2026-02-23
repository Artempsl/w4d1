# NormalObjects - Strict Complaint Processor (LangGraph)

**Lab 2: Structured, Rule-Based Complaint Processing using LangGraph State Machine**

A production-grade complaint processing system implementing Bloyce's Protocol for the Downside Up Complaint Bureau. This system demonstrates structured workflow management using LangGraph, ensuring consistent, traceable, and compliant complaint handling.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Bloyce's Protocol Rules](#bloyces-protocol-rules)
- [Workflow Visualization](#workflow-visualization)
- [Testing](#testing)
- [Comparison with LangChain](#comparison-with-langchain)
- [Technical Details](#technical-details)
- [Lab Context](#lab-context)

---

## 🎯 Overview

This project implements a **deterministic, rule-based complaint processing workflow** for handling complaints from the Downside Up universe (Stranger Things inspired). Unlike creative agent-based systems (LangChain), this system follows strict protocols to ensure:

- ✅ **Compliance**: Every complaint follows Bloyce's Protocol
- ✅ **Consistency**: Same complaint type = same processing path
- ✅ **Traceability**: Complete audit trail of all decisions
- ✅ **Predictability**: Deterministic workflow execution

**Use Case**: Regulated environments requiring auditable, consistent complaint processing (customer service, compliance, healthcare, legal).

---

## ✨ Features

### Core Functionality

- **5 Complaint Categories**: Portal, Monster, Psychic, Environmental, Other
- **Rule-Based Categorization**: Keyword matching with phrase prioritization
- **Duplicate Detection**: 30-day window with automatic linking
- **Category-Specific Validation**: Enforced business rules per category
- **Structured Investigation**: Template-based evidence generation
- **Standards-Compliant Resolution**: References Downside Up Standard Procedures
- **Customer Satisfaction Tracking**: Based on effectiveness ratings

### Workflow Features

- **Conditional Routing**: Early termination for invalid/escalated complaints
- **State Machine Architecture**: LangGraph-powered workflow
- **Complete Audit Trail**: Full workflow_path tracking
- **Dual Logging**: Console + file (`complaints.log`)
- **Effectiveness Ratings**: HIGH/MEDIUM/LOW with follow-up requirements
- **Escalation Handling**: OTHER category auto-escalates for manual review

---

## 🏗️ Architecture

### LangGraph State Machine

```
START
  ↓
┌─────────────────┐
│  intake_node    │ ← Categorize, detect duplicates
└────────┬────────┘
         ↓
┌─────────────────┐
│ validation_node │ ← Apply category-specific rules
└────────┬────────┘
         ↓
    [DECISION]
    ╱        ╲
invalid     valid
   ↓           ↓
  END    ┌─────────────────┐
         │investigation_node│ ← Generate evidence
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
         │ resolution_node  │ ← Apply standard procedures
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
         │  closure_node    │ ← Log completion, check satisfaction
         └────────┬────────┘
                  ↓
                 END
```

### State Object

```python
ComplaintState = {
    complaint_id: str              # Unique identifier
    complaint_text: str            # Original input
    category: ComplaintCategory    # portal/monster/psychic/environmental/other
    is_valid: bool                 # Validation result
    is_duplicate: bool             # 30-day duplicate detection
    linked_complaint_id: str       # Reference to original if duplicate
    investigation_evidence: str    # Investigation findings
    resolution: str                # Applied solution
    effectiveness_rating: str      # high/medium/low
    status: str                    # processing/closed/rejected/escalated
    customer_satisfied: bool       # Satisfaction check
    workflow_path: List[str]       # Audit trail
}
```

---

## 📁 Project Structure

```
w4d1/
├── .venv/                          # Isolated virtual environment
├── .env.example                    # Environment variable template
├── .gitignore                      # Git exclusions
├── normalobjects_langgraph.py      # Main implementation
├── requirements.txt                # Pinned dependencies
├── complaints.log                  # Execution log file
├── COMPARISON.md                   # LangChain vs LangGraph analysis
└── README.md                       # This file
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.14+** (tested with 3.14.2)
- **Windows** (PowerShell)

### Step 1: Clone/Navigate to Project

```powershell
cd c:\Users\kupit\w4\w4d1
```

### Step 2: Create Virtual Environment

```powershell
python -m venv .venv
```

### Step 3: Activate Virtual Environment

```powershell
# PowerShell (if execution policy allows)
.\.venv\Scripts\Activate.ps1

# Alternative (bypass execution policy)
& .\.venv\Scripts\python.exe
```

### Step 4: Install Dependencies

```powershell
& .\.venv\Scripts\pip.exe install -r requirements.txt
```

**Core Dependencies**:
- `langgraph==1.0.9` - State machine workflow framework
- `langchain-core==1.2.15` - Base abstractions
- `pydantic==2.12.5` - Data validation

**Total packages**: 30 (including transitive dependencies)

### Step 5: Environment Variables (Optional)

This project uses **rule-based logic** and does not require OpenAI API keys. If you want to extend it with LLM features later:

```powershell
# Copy template
cp .env.example .env

# Edit .env and add your API key
# OPENAI_API_KEY=your_key_here
```

---

## 💻 Usage

### Run End-to-End Tests

```powershell
& .\.venv\Scripts\python.exe normalobjects_langgraph.py
```

**This will execute**:
- All stage validation tests (Stages 2-7)
- Comprehensive end-to-end testing (Stage 8)
- Process all 5 complaint categories
- Demonstrate duplicate detection
- Generate complete logs

**Output**: Console output + `complaints.log` file

### Example Output

```
======================================================================
COMPLAINT SUMMARY: 5fa9d64a
======================================================================
Text: The Downside Up portal opens at different times each day. How do I predict when?...
Category: portal
Status: closed
Valid: True
Validation: Valid portal complaint with location reference and timing reference
Resolution Effectiveness: high
Customer Satisfaction: ✓ Satisfied

Workflow Path: intake → validate → investigate → resolve → close
======================================================================
```

### Process Custom Complaint

```python
from normalobjects_langgraph import build_complaint_workflow, create_initial_state

# Build workflow
workflow = build_complaint_workflow()

# Create complaint
state = create_initial_state("Portal behaves strangely at midnight in Hawkins Lab")

# Execute workflow
final_state = None
for state_update in workflow.stream(state):
    final_state = list(state_update.values())[0]

# Check results
print(f"Status: {final_state['status']}")
print(f"Category: {final_state['category'].value}")
print(f"Path: {' → '.join(final_state['workflow_path'])}")
```

---

## 📜 Bloyce's Protocol Rules

### Intake Rules

- ✅ Categorize into exactly one of 5 categories
- ✅ Detect duplicates within 30-day window
- ✅ Link duplicates to original complaint
- ✅ Flag complaints missing essential details

### Validation Rules

| Category | Requirement |
|----------|-------------|
| **Portal** | Must reference location OR timing anomalies |
| **Monster** | Must describe creature behavior or interactions |
| **Psychic** | Must reference ability AND limitation |
| **Environmental** | Must connect to electricity, weather, or physical phenomena |
| **Other** | Automatically escalated for manual review |

### Investigation Rules

- ✅ Portal: Temporal patterns, location consistency, environmental factors
- ✅ Monster: Behavioral data, interaction patterns, triggers
- ✅ Psychic: Ability specs, limitations, contextual factors
- ✅ Environmental: Power line activity, atmospheric conditions, correlations
- ✅ Must produce documented evidence before resolution

### Resolution Rules

- ✅ Must reference Downside Up Standard Procedures
- ✅ Must include effectiveness rating (high/medium/low)
- ✅ Environmental/Monster may require specialist escalation
- ✅ Cannot be applied without investigation evidence

### Closure Rules

- ✅ Confirm resolution applied
- ✅ Verify customer satisfaction
- ✅ Log: category, resolution, outcome, timestamp
- ✅ Low effectiveness ratings → 30-day follow-up required
- ✅ Cannot skip workflow steps

---

## 📊 Workflow Visualization

### Valid Complaint (Full Workflow)

```
Complaint: "Portal opens at different times in Hawkins Lab"
  ↓
intake    : Categorized as PORTAL, no duplicate
  ↓
validate  : ✓ Valid (location + timing reference)
  ↓
investigate: Generated portal investigation report (702 chars)
  ↓
resolve   : Applied Protocol 4.2.1, effectiveness: HIGH
  ↓
close     : Closed, customer satisfied
  ↓
Path: intake → validate → investigate → resolve → close
```

### Invalid Complaint (Early Termination)

```
Complaint: "There's a portal"
  ↓
intake    : Categorized as PORTAL, no duplicate
  ↓
validate  : ✗ Invalid (lacks location/timing details)
  ↓
END (rejected)
  ↓
Path: intake → validate
```

### Duplicate Complaint

```
Complaint: "Portal opens at random times in Hawkins Lab" (2nd submission)
  ↓
intake    : ⚠️ Duplicate detected, linked to 7ca4d6ea
  ↓
validate  : ✓ Valid (duplicate - skip full validation)
  ↓
investigate: Refer to original investigation
  ↓
resolve   : Apply same resolution as original
  ↓
close     : Closed as duplicate
  ↓
Path: intake → validate → investigate → resolve → close
```

---

## 🧪 Testing

### Run All Tests

```powershell
& .\.venv\Scripts\python.exe normalobjects_langgraph.py
```

### Test Coverage

**Stage 2**: State definitions and helper functions
- ✅ State initialization
- ✅ Text normalization
- ✅ Duplicate detection

**Stage 3**: Intake node
- ✅ All 5 category classifications
- ✅ Duplicate detection (30-day window)

**Stage 4**: Validation node
- ✅ Category-specific validation rules
- ✅ Invalid complaint rejection
- ✅ OTHER category escalation

**Stage 5**: Investigation node
- ✅ Evidence generation for all categories
- ✅ Investigation skipped for invalid complaints
- ✅ Duplicate reference handling

**Stage 6**: Resolution & closure nodes
- ✅ Resolution application with effectiveness ratings
- ✅ Customer satisfaction tracking
- ✅ Full workflow path verification

**Stage 7**: LangGraph assembly
- ✅ Workflow compilation
- ✅ Conditional routing
- ✅ Early termination paths

**Stage 8**: End-to-end testing
- ✅ All 5 complaint categories
- ✅ Duplicate detection workflow
- ✅ Valid and invalid complaints
- ✅ Workflow path visualization

### Expected Results

```
Total complaints processed: 7
Complaints by Category:
  portal: 3
  monster: 1
  psychic: 1
  environmental: 1
  other: 1

Complaints by Status:
  closed: 5
  closed-duplicate: 1
  escalated: 1
```

---

## 🔄 Comparison with LangChain

See [COMPARISON.md](COMPARISON.md) for detailed analysis.

**TL;DR:**

| Aspect | LangChain | LangGraph (This Project) |
|--------|-----------|--------------------------|
| **Approach** | Creative agent | Structured workflow |
| **Consistency** | Variable | Deterministic |
| **Auditability** | Limited | Complete |
| **Best For** | Exploration | Compliance |

**Why LangGraph for NormalObjects?**
- ✅ Bloyce's Protocol requires strict compliance
- ✅ Audit trails are mandatory
- ✅ Consistent customer treatment
- ✅ Regulatory oversight

---

## 🔧 Technical Details

### State Management

The workflow uses `ComplaintState` TypedDict to maintain immutable state across nodes:

```python
class ComplaintState(TypedDict):
    complaint_id: str
    complaint_text: str
    category: Optional[ComplaintCategory]
    is_valid: bool
    # ... (full definition in code)
```

### Categorization Algorithm

**Keyword-based with multi-word phrase priority**:

```python
# "power lines" (2 words) scores higher than "power" (1 word)
score = sum(len(keyword.split()) for keyword in matched_keywords)
```

**Example**:
- ❌ "Psychic power exists" → power (1) → psychic
- ✅ "Power lines flicker" → power lines (2) → environmental

### Duplicate Detection

**30-day window with normalized text**:

```python
normalized = " ".join(text.lower().strip().split())
if normalized in history:
    time_diff = current_time - original_timestamp
    if time_diff <= timedelta(days=30):
        return True, original_id
```

### Logging Configuration

**Dual output (console + file)**:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('complaints.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
```

---

## 📚 Lab Context

**Course**: Backend Development (Week 4, Day 1)  
**Lab Series**: NormalObjects - Complaint Processing Systems  
**Lab 2 Focus**: Structured workflows with LangGraph  

**Learning Objectives**:
- ✅ Build structured agent workflow using LangGraph state machine
- ✅ Implement defined nodes and edges for complaint processing
- ✅ Create rule-based complaint processing system
- ✅ Understand state management in agentic workflows
- ✅ Compare structured LangGraph approach with freeform LangChain agents

**Prerequisites**:
- Understanding of LangGraph concepts
- Familiarity with state machines
- Experience with LangChain (from previous lab)
- Basic Python programming

**Estimated Time**: 120-150 minutes

---

## 🎓 Success Criteria

- ✅ Successfully built LangGraph state machine
- ✅ Workflow follows defined steps (intake → validate → investigate → resolve → close)
- ✅ State is properly managed throughout workflow
- ✅ System provides traceable, consistent results
- ✅ Handles both valid and invalid complaints
- ✅ Duplicate detection functional
- ✅ Code is well-documented
- ✅ Comparison document complete

---

## 🛠️ Troubleshooting

### Virtual Environment Issues

**Problem**: Cannot activate .venv  
**Solution**: Use direct Python execution:
```powershell
& .\.venv\Scripts\python.exe normalobjects_langgraph.py
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'langgraph'`  
**Solution**: Ensure you're using .venv Python:
```powershell
& .\.venv\Scripts\pip.exe install -r requirements.txt
```

### Log File Permissions

**Problem**: Cannot write to `complaints.log`  
**Solution**: Check file permissions or delete existing log file

---

## 📝 License

Educational project for laboratory work.

---

## 👤 Author

NormalObjects Lab Series  
Date: February 23, 2026

---

## 🔗 Additional Resources

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **LangChain Core**: https://python.langchain.com/docs/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **State Machine Patterns**: Design patterns for workflow systems

---

## 📞 Support

For lab-related questions, refer to:
- Lab instructions document
- COMPARISON.md for LangChain vs LangGraph analysis
- Code comments in normalobjects_langgraph.py

---

**🎉 Project Status: Production-Ready**

All stages completed, tested, and validated. System is ready for demonstration and GitHub submission.
