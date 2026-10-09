# FY26 AI Sales Play Decision Tree

This reference helps in selecting the appropriate AI sales play based on
customer needs.

## Decision Tree Diagram

```mermaid
graph TD
    Start([Start]) --> Scale["Scale AI Apps & Agents (Primary)"]
    Scale -->|No| Q1{"Need to embed AI directly into every employee's daily workflow?"}
    Q1 -->|Yes| AWT["Agentic Workplace Transformation (Primary)"]
    Q1 -->|No| Q2{"Need to transform search, commerce & service interactions into seamless customer journey?"}
    Q2 -->|Yes| GECE["GE for Customer Experience (Growth)"]
    Q2 -->|No| Q3{"Need to train/tune model on proprietary data for IP moat?"}
    Q3 -->|Yes| YBYM["Your Business, Your Models (Growth)"]
    Q3 -->|No| Q4{"Need for creative workflow automation?"}
    Q4 -->|Yes| LGM["Leverage Gen Media in Your Business (Growth)"]
    Q4 -->|No| Q5{"Need pre-built vertical agents?"}
    Q5 -->|Yes| AAP["Applied AI Portfolio (Emerging)"]
    Q5 -->|No| Return["Return to primary play"]
    Return --> Scale
```

## Details

### 1. Scale AI Apps & Agents [Primary]

-   **Criteria**: Customer needs to build, deploy or consolidate apps/agents
    into a production-ready, governed platform. Needs access to SOTA (State Of
    The Art) models.
-   **Keywords**: Gemini, Anthropic, API Consumption on Vertex AI platform.
-   **Note**: *ALWAYS START HERE*

### 2. Agentic Workplace Transformation [Primary]

-   **Criteria**: Need to embed AI directly into every employee's daily
    workflow.
-   **Action**: Create agentic workplace transformation, empowering every
    employee across workflows with AI for internal productivity purposes.
-   **Keywords**: Gemini Enterprise, Google Workspace.

### 3. GE for Customer Experience [Growth]

-   **Criteria**: Need to transform search, commerce & service interactions into
    a seamless customer journey.
-   **Keywords**: Gemini Enterprise for Customer Experience, VAIS, CES, Shopping
    Agent. Includes food ordering.

### 4. Your Business, Your Models [Growth]

-   **Criteria**: Need to train/tune model on proprietary data for IP moat.
-   **Action**: Customer developing proprietary model and values time to
    production with a fully managed service.
-   **Keywords**: Agent Platform, GPU/TPU.

### 5. Leverage Gen Media in Your Business [Growth]

-   **Criteria**: Need for creative workflow automation.
-   **Action**: Content generation or creative editing tools. ISVs and software
    vendors for creative processes, consumer content creation / publishing apps
    & tools.
-   **Keywords**: Veo, Imagen, Lyria, Chirp.

### 6. Applied AI Portfolio [Emerging]

-   **Criteria**: Need pre-built vertical agents (Auto).
-   **Action**: Customer wants "ready-to-deploy" agent for a specific industry
    (Auto) function.
