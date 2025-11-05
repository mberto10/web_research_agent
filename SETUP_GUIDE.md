# Complete Setup Guide for Web Research Agent

## Prerequisites

### 1. Python Requirements
- **Python 3.12+** is required
- Virtual environment recommended

### 2. API Keys Required

You need the following API keys for the daily news briefing to work:

| Service | Environment Variable | Purpose | Get Key From |
|---------|---------------------|---------|--------------|
| OpenAI | `OPENAI_API_KEY` | LLM analysis, QC, summarization | https://platform.openai.com/api-keys |
| Perplexity (Sonar) | `SONAR_API_KEY` or `PERPLEXITY_API_KEY` | Sonar search (broad overview) | https://docs.perplexity.ai |
| Exa | `EXA_API_KEY` | Semantic search, answers | https://exa.ai |

## Installation Steps

### Step 1: Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd web_research_agent

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install core dependencies
pip install langgraph>=0.6 pydantic>=2.0 pyyaml>=6.0 jsonschema>=4.0

# Install optional dependencies for search tools
pip install exa-py openai

# Or install everything at once
pip install -e ".[all]"
```

### Step 3: Set Environment Variables

#### Windows (Command Prompt)
```cmd
set OPENAI_API_KEY=your-openai-api-key-here
set EXA_API_KEY=your-exa-api-key-here
set SONAR_API_KEY=your-perplexity-api-key-here
```

#### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your-openai-api-key-here"
$env:EXA_API_KEY="your-exa-api-key-here"
$env:SONAR_API_KEY="your-perplexity-api-key-here"
```

#### Mac/Linux
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
export EXA_API_KEY="your-exa-api-key-here"
export SONAR_API_KEY="your-perplexity-api-key-here"
```

#### Using .env file (Recommended)
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-openai-api-key-here
EXA_API_KEY=your-exa-api-key-here
SONAR_API_KEY=your-perplexity-api-key-here
# Or, alternatively
PERPLEXITY_API_KEY=your-perplexity-api-key-here
```

Then load it using python-dotenv:
```bash
pip install python-dotenv
```

## Verifying Your Setup

### Step 4: Run the Setup Verification Script

```bash
python verify_setup.py
```

This will check:
- Python version
- Required packages
- API key configuration
- Tool registration
- Strategy loading

### Step 5: Test Daily News Briefing

```bash
python run_daily_briefing.py --topic "artificial intelligence"
```

## Project Structure

```
web_research_agent/
├── config/
│   └── settings.yaml         # LLM configurations and prompts
├── core/
│   ├── graph.py             # Main workflow engine
│   ├── state.py             # State management
│   ├── scope.py             # Request categorization
│   ├── utils.py             # Utilities (including date parsing)
│   └── config.py            # Configuration loader
├── strategies/
│   ├── daily_news_briefing.yaml  # Your new strategy
│   ├── company/             # Company research strategies
│   ├── news/                # News strategies
│   └── general/             # General strategies
├── tools/
│   ├── sonar.py             # Perplexity Sonar adapter
│   ├── exa.py               # Exa search adapter
│   ├── llm_analyzer.py      # LLM analysis tool
│   ├── http.py              # Web scraper
│   └── parse.py             # Content parser

```

## Common Issues and Solutions

### Issue: "No module named 'openai'"
**Solution:** Install the openai package
```bash
pip install openai
```

### Issue: "No module named 'exa_py'"
**Solution:** Install the exa-py package
```bash
pip install exa-py
```

### Issue: "Sonar API key required"
**Solution:** Set `SONAR_API_KEY` or `PERPLEXITY_API_KEY` (Perplexity Sonar API)

### Issue: "Strategy not found"
**Solution:** Ensure the strategy YAML file exists in the strategies/ directory

### Issue: Unicode encoding errors on Windows
**Solution:** Set console encoding
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

## Testing Your Configuration

### Minimal Test
```python
from tools import SonarAdapter, ExaAdapter
from core.llm_analyzer import LLMAnalyzerAdapter

# Test each tool individually
try:
    sonar = SonarAdapter()
    print("✓ Sonar configured")
except Exception as e:
    print(f"✗ Sonar error: {e}")

try:
    exa = ExaAdapter()
    print("✓ Exa configured")
except Exception as e:
    print(f"✗ Exa error: {e}")

try:
    llm = LLMAnalyzerAdapter()
    print("✓ LLM Analyzer configured")
except Exception as e:
    print(f"✗ LLM Analyzer error: {e}")
```

### Full Workflow Test
```python
from core.graph import build_graph
from core.state import State
from tools import register_default_adapters

# Register all tools
register_default_adapters(silent=False)

# Build and run workflow
graph = build_graph()
state = State(
    user_request="Daily briefing on renewable energy",
    strategy_slug="daily_news_briefing"
)
result = graph.invoke(state)
print(f"Generated {len(result.sections)} sections")
```

## Optional Configuration

### Custom LLM Models
Edit `config/settings.yaml` to use different models:
```yaml
llm:
  defaults:
    fill:
      model: gpt-4o-mini  # or gpt-4, gpt-3.5-turbo
    analyzer:
      model: gpt-4       # for better synthesis
```

### Strategy Customization
Modify `strategies/daily_news_briefing.yaml` to adjust:
- Number of search results
- Search parameters
- Output structure
- Quality thresholds

## Next Steps

1. **Run a test briefing**: 
   ```bash
   python run_daily_briefing.py --topic "your topic"
   ```

2. **Customize the strategy**: Edit `strategies/daily_news_briefing.yaml`

3. **Create new strategies**: Copy and modify existing YAML files

4. **Add new tools**: Implement the ToolAdapter protocol in `tools/`

## Support

For issues:
1. Check API keys are set correctly
2. Verify all dependencies are installed
3. Check the logs for specific error messages
4. Review the test files in `tests/` for examples
