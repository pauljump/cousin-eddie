"""
Investment Thesis Generator

Uses LLM (OpenAI GPT-4) to synthesize all signals into actionable investment thesis.
This is the CORE VALUE PROP - turning 100+ signals into coherent narrative.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

from openai import OpenAI
from loguru import logger

from ..models.base import SessionLocal
from ..models.signal import SignalModel
from ..core.company import Company


class InvestmentThesis:
    """Structured investment thesis output"""

    def __init__(
        self,
        company_id: str,
        overall_verdict: str,  # "BULLISH", "BEARISH", "NEUTRAL"
        conviction: int,  # 0-100
        bull_case: List[str],
        bear_case: List[str],
        key_catalysts: List[str],
        synthesis: str,
        recommended_action: str,
        position_size: str,
        raw_thesis: str,  # Full LLM output
    ):
        self.company_id = company_id
        self.overall_verdict = overall_verdict
        self.conviction = conviction
        self.bull_case = bull_case
        self.bear_case = bear_case
        self.key_catalysts = key_catalysts
        self.synthesis = synthesis
        self.recommended_action = recommended_action
        self.position_size = position_size
        self.raw_thesis = raw_thesis
        self.generated_at = datetime.utcnow()

    def __str__(self):
        return f"""
{'='*80}
INVESTMENT THESIS: {self.company_id}
Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}
{'='*80}

{self.raw_thesis}

{'='*80}
"""


class ThesisGenerator:
    """Generate investment thesis from all available signals"""

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize thesis generator.

        Args:
            openai_api_key: OpenAI API key. If None, will use environment variable.
        """
        self.client = OpenAI(api_key=openai_api_key)
        self.model = "gpt-4-turbo-preview"  # GPT-4 Turbo model

    async def generate_thesis(
        self,
        company: Company,
        lookback_days: int = 90
    ) -> InvestmentThesis:
        """
        Generate investment thesis for a company based on all available signals.

        Args:
            company: Company to analyze
            lookback_days: How many days of signals to consider

        Returns:
            InvestmentThesis object with structured output
        """
        logger.info(f"Generating investment thesis for {company.ticker}")

        # Fetch all signals for this company
        signals = self._fetch_signals(company.id, lookback_days)

        if not signals:
            logger.warning(f"No signals found for {company.id}")
            return None

        # Organize signals by category
        signal_summary = self._organize_signals(signals)

        # Build prompt for LLM
        prompt = self._build_prompt(company, signal_summary, signals)

        # Call OpenAI API
        logger.info(f"Calling OpenAI API to synthesize {len(signals)} signals...")
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4000,
            temperature=0.3,  # Lower temperature for more analytical output
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        thesis_text = response.choices[0].message.content

        # Parse structured output from thesis
        parsed = self._parse_thesis(thesis_text)

        thesis = InvestmentThesis(
            company_id=company.id,
            overall_verdict=parsed.get('verdict', 'NEUTRAL'),
            conviction=parsed.get('conviction', 50),
            bull_case=parsed.get('bull_case', []),
            bear_case=parsed.get('bear_case', []),
            key_catalysts=parsed.get('catalysts', []),
            synthesis=parsed.get('synthesis', ''),
            recommended_action=parsed.get('action', 'HOLD'),
            position_size=parsed.get('position_size', 'NORMAL'),
            raw_thesis=thesis_text,
        )

        logger.info(f"✓ Generated thesis: {thesis.overall_verdict} (Conviction: {thesis.conviction}/100)")

        return thesis

    def _fetch_signals(self, company_id: str, lookback_days: int) -> List[SignalModel]:
        """Fetch all signals for company within lookback period"""
        session = SessionLocal()

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

            signals = session.query(SignalModel).filter(
                SignalModel.company_id == company_id,
                SignalModel.timestamp >= cutoff_date
            ).order_by(SignalModel.timestamp.desc()).all()

            logger.info(f"Fetched {len(signals)} signals for {company_id}")
            return signals

        finally:
            session.close()

    def _organize_signals(self, signals: List[SignalModel]) -> Dict[str, Any]:
        """Organize signals by category and type for easier analysis"""

        # Group by category
        by_category = defaultdict(list)
        by_type = defaultdict(list)

        for signal in signals:
            by_category[signal.category].append(signal)
            by_type[signal.signal_type].append(signal)

        # Get latest signal of each type
        latest_by_type = {}
        for signal_type, type_signals in by_type.items():
            latest_by_type[signal_type] = max(type_signals, key=lambda s: s.timestamp)

        # Calculate category averages
        category_scores = {}
        for category, cat_signals in by_category.items():
            scores = [s.score for s in cat_signals]
            category_scores[category] = {
                'avg_score': sum(scores) / len(scores),
                'count': len(scores),
                'latest': max(cat_signals, key=lambda s: s.timestamp)
            }

        return {
            'by_category': dict(by_category),
            'by_type': dict(by_type),
            'latest_by_type': latest_by_type,
            'category_scores': category_scores,
            'total_signals': len(signals)
        }

    def _build_prompt(
        self,
        company: Company,
        signal_summary: Dict[str, Any],
        signals: List[SignalModel]
    ) -> str:
        """Build comprehensive prompt for Claude"""

        # Get EDGAR ground truth signals (most important)
        edgar_signals = signal_summary['by_category'].get('regulatory', [])
        edgar_latest = sorted(edgar_signals, key=lambda s: s.timestamp, reverse=True)[:10]

        # Get alternative signals
        alternative_signals = []
        for cat in ['web_digital', 'alternative', 'workforce']:
            alternative_signals.extend(signal_summary['by_category'].get(cat, []))
        alt_latest = sorted(alternative_signals, key=lambda s: s.timestamp, reverse=True)[:15]

        # Build EDGAR summary
        edgar_summary = self._format_signals(edgar_latest, "EDGAR GROUND TRUTH")

        # Build alternative signals summary
        alt_summary = self._format_signals(alt_latest, "ALTERNATIVE SIGNALS")

        # Get category scores
        cat_scores = signal_summary['category_scores']

        prompt = f"""You are a quantitative analyst at a top hedge fund synthesizing alternative data signals for {company.name} ({company.ticker}).

Your task is to analyze all available signals and generate a comprehensive, actionable investment thesis.

# SIGNAL OVERVIEW

**Total Signals Analyzed:** {signal_summary['total_signals']}
**Time Period:** Last 90 days
**Signal Categories:**
{self._format_category_scores(cat_scores)}

---

# EDGAR GROUND TRUTH (Legally Required Disclosures)

These are quarterly/annual financial statements - THE SOURCE OF TRUTH.
All other signals should validate or contradict these fundamentals.

{edgar_summary}

---

# ALTERNATIVE SIGNALS (Real-Time Indicators)

These signals provide real-time data between quarterly earnings reports.
They should either CONFIRM or CONTRADICT the EDGAR truth.

{alt_summary}

---

# YOUR ANALYSIS TASK

Generate a comprehensive investment thesis with the following structure:

## 1. OVERALL VERDICT
- State: BULLISH, BEARISH, or NEUTRAL
- Conviction: 0-100 (where 100 = highest conviction)
- One-sentence summary

## 2. BULL CASE
- List 3-5 strongest bullish arguments
- Each must cite specific signal data (e.g., "Q3 net margin 49% per EDGAR 10-Q")
- Focus on EDGAR truth validated by alternative signals

## 3. BEAR CASE
- List 3-5 biggest risks/concerns
- Each must cite specific signal data
- Include any contradictions between signal types

## 4. SIGNAL SYNTHESIS
- How do alternative signals validate or contradict EDGAR truth?
- Identify any major contradictions and explain them
- Show cause-and-effect chains (e.g., "App ratings 4.90/5 → Net margin 49%")

## 5. KEY CATALYSTS TO MONITOR
- What events/signals to watch going forward?
- What would change your thesis?
- Leading indicators to track

## 6. RECOMMENDED ACTION
- Action: BUY, SELL, or HOLD
- Position Size: SMALL (1-5%), NORMAL (5-10%), LARGE (10-15%), or AVOID
- Entry/exit criteria
- Stop loss level (if applicable)

---

# ANALYSIS GUIDELINES

1. **EDGAR TRUTH > Alternative Signals**
   - Financial statements are legally required, high confidence
   - If alternative signals contradict EDGAR, trust EDGAR (but investigate why)

2. **Look for Validation**
   - Best case: EDGAR shows strong fundamentals AND alternative signals confirm
   - Red flag: EDGAR weak but alternative signals positive (false hope)
   - Opportunity: EDGAR strong but alternative signals negative (market inefficiency)

3. **Be Specific and Data-Driven**
   - Always cite numbers: "Revenue growth +6.5% QoQ" not "revenue growing"
   - Use actual signal scores and timestamps
   - Quantify everything possible

4. **Be Actionable**
   - Clear buy/sell/hold recommendation
   - Specific entry/exit criteria
   - Position sizing guidance

5. **Identify Contradictions**
   - If signals conflict, explicitly call this out
   - Explain what the contradiction means
   - Which signal to trust and why

Generate the investment thesis now. Be thorough, analytical, and actionable.
"""

        return prompt

    def _format_signals(self, signals: List[SignalModel], title: str) -> str:
        """Format signals for prompt"""
        if not signals:
            return f"**{title}:** No signals available"

        output = f"**{title}:**\n\n"

        for sig in signals:
            date_str = sig.timestamp.strftime('%Y-%m-%d')
            score_str = f"{sig.score:+d}" if sig.score else "0"

            output += f"- **{sig.signal_type}** ({date_str})\n"
            output += f"  - Score: {score_str} | Confidence: {sig.confidence:.2f}\n"
            output += f"  - {sig.description}\n"

            # Add key raw values if available
            if sig.raw_value and isinstance(sig.raw_value, dict):
                key_fields = ['revenue', 'net_margin', 'ocf_margin', 'growth_rate', 'total_value']
                relevant = {k: v for k, v in sig.raw_value.items() if k in key_fields}
                if relevant:
                    output += f"  - Data: {json.dumps(relevant, default=str)}\n"

            output += "\n"

        return output

    def _format_category_scores(self, cat_scores: Dict[str, Any]) -> str:
        """Format category scores"""
        output = ""

        for category, data in sorted(cat_scores.items()):
            avg_score = data['avg_score']
            count = data['count']

            sentiment = "BULLISH" if avg_score > 30 else "BEARISH" if avg_score < -30 else "NEUTRAL"

            output += f"- **{category.upper()}**: {avg_score:+.0f} avg score ({count} signals) - {sentiment}\n"

        return output

    def _parse_thesis(self, thesis_text: str) -> Dict[str, Any]:
        """Parse structured elements from thesis text"""

        # This is a simple parser - could be made more sophisticated
        parsed = {
            'verdict': 'NEUTRAL',
            'conviction': 50,
            'bull_case': [],
            'bear_case': [],
            'catalysts': [],
            'synthesis': '',
            'action': 'HOLD',
            'position_size': 'NORMAL'
        }

        # Extract verdict
        if 'BULLISH' in thesis_text.upper():
            parsed['verdict'] = 'BULLISH'
        elif 'BEARISH' in thesis_text.upper():
            parsed['verdict'] = 'BEARISH'

        # Extract conviction (look for pattern like "Conviction: 85")
        import re
        conviction_match = re.search(r'(?:Conviction|conviction)[:\s]+(\d+)', thesis_text)
        if conviction_match:
            parsed['conviction'] = int(conviction_match.group(1))

        # Extract action
        if 'BUY' in thesis_text.upper() and 'SELL' not in thesis_text.upper():
            parsed['action'] = 'BUY'
        elif 'SELL' in thesis_text.upper():
            parsed['action'] = 'SELL'

        # Could add more sophisticated parsing here

        return parsed


# CLI function for easy testing
async def generate_thesis_cli(company_ticker: str):
    """Generate thesis from command line"""
    from ..core.company import get_registry

    registry = get_registry()
    company = registry.get(company_ticker)

    if not company:
        print(f"Company {company_ticker} not found in registry")
        return

    generator = ThesisGenerator()
    thesis = await generator.generate_thesis(company)

    if thesis:
        print(thesis)
    else:
        print(f"Could not generate thesis for {company_ticker}")


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.synthesis.thesis_generator <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1]
    asyncio.run(generate_thesis_cli(ticker))
