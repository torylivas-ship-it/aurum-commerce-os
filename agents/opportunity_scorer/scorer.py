"""
Opportunity Scorer — scores every product candidate using the formula:
  30% Demand + 25% Gross Profit Margin + 20% Competition + 15% Supplier + 10% Shipping

Every product also gets a Confidence Score and Risk Score.
Hard rejects products that fail any business rule.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProductCandidate:
    name: str
    supplier_cost: float
    shipping_cost: float
    estimated_selling_price: float

    # Demand signals (0-100)
    trend_score: float = 0.0          # How trending is this product?
    search_volume_score: float = 0.0  # Search volume health
    social_signal_score: float = 0.0  # Social media buzz
    sales_velocity_score: float = 0.0 # Velocity of sales on other platforms

    # Competition signals (0-100, higher = LESS competition = better)
    competition_score: float = 0.0    # Inverse: low competition = high score
    market_saturation: float = 0.0    # How saturated is the market?

    # Supplier signals (0-100)
    supplier_rating: float = 0.0
    supplier_delivery_score: float = 0.0
    supplier_inventory_score: float = 0.0

    # Shipping signals (0-100, higher = better)
    shipping_days: int = 30
    shipping_reliability: float = 0.0

    # Confidence factors
    data_sources_count: int = 1
    data_freshness_days: int = 7
    trend_consistency_score: float = 0.0

    # Evidence
    evidence: Dict = field(default_factory=dict)
    source_platform: str = ""
    source_url: str = ""
    image_url: str = ""
    category: str = ""
    supplier_name: str = ""
    supplier_url: str = ""


@dataclass
class ScoreResult:
    # Primary scores (0-100)
    opportunity_score: float
    confidence_score: float
    risk_score: float

    # Component scores
    demand_score: float
    margin_score: float
    competition_score: float
    supplier_score: float
    shipping_score: float

    # Financials
    gross_margin: float
    estimated_selling_price: float
    supplier_cost: float
    shipping_cost: float
    profit_per_unit: float

    # Decision
    is_viable: bool
    rejection_reasons: List[str]
    recommendation: str
    explanation: str

    # Breakdown
    score_breakdown: Dict


class OpportunityScorer:
    """
    Scores product candidates. Stateless — call score() per product.
    """

    # Weights (must sum to 1.0)
    WEIGHTS = {
        "demand":     0.30,
        "margin":     0.25,
        "competition": 0.20,
        "supplier":   0.15,
        "shipping":   0.10,
    }

    def score(self, candidate: ProductCandidate) -> ScoreResult:
        rejection_reasons: List[str] = []

        # ── 1. Financial calculations ─────────────────────────────────────────
        total_cost = candidate.supplier_cost + candidate.shipping_cost
        profit_per_unit = candidate.estimated_selling_price - total_cost
        gross_margin = profit_per_unit / candidate.estimated_selling_price if candidate.estimated_selling_price > 0 else 0.0

        # ── 2. Hard reject rules ──────────────────────────────────────────────
        if gross_margin < settings.min_gross_margin:
            rejection_reasons.append(
                f"Gross margin {gross_margin:.1%} below minimum {settings.min_gross_margin:.0%}"
            )

        if candidate.supplier_rating > 0 and candidate.supplier_rating < settings.min_supplier_rating:
            rejection_reasons.append(
                f"Supplier rating {candidate.supplier_rating:.1f} below minimum {settings.min_supplier_rating}"
            )

        if candidate.shipping_days > settings.max_shipping_days:
            rejection_reasons.append(
                f"Shipping {candidate.shipping_days} days exceeds maximum {settings.max_shipping_days} days"
            )

        if candidate.estimated_selling_price <= 0:
            rejection_reasons.append("Estimated selling price must be > 0")

        # ── 3. Component scores ───────────────────────────────────────────────
        demand_score = self._calc_demand(candidate)
        margin_score = self._calc_margin(gross_margin)
        competition_score = self._calc_competition(candidate)
        supplier_score = self._calc_supplier(candidate)
        shipping_score = self._calc_shipping(candidate)

        # ── 4. Opportunity score (weighted sum) ───────────────────────────────
        opportunity_score = (
            demand_score      * self.WEIGHTS["demand"] +
            margin_score      * self.WEIGHTS["margin"] +
            competition_score * self.WEIGHTS["competition"] +
            supplier_score    * self.WEIGHTS["supplier"] +
            shipping_score    * self.WEIGHTS["shipping"]
        )

        # ── 5. Confidence score ────────────────────────────────────────────────
        confidence_score = self._calc_confidence(candidate)

        # ── 6. Risk score (higher = more risk) ────────────────────────────────
        risk_score = self._calc_risk(candidate, gross_margin)

        # ── 7. Viability check ────────────────────────────────────────────────
        if confidence_score < settings.min_confidence_score:
            rejection_reasons.append(
                f"Confidence score {confidence_score:.0f} below minimum {settings.min_confidence_score:.0f}"
            )

        is_viable = len(rejection_reasons) == 0
        recommendation = self._recommend(opportunity_score, is_viable, rejection_reasons)
        explanation = self._explain(
            opportunity_score, confidence_score, risk_score,
            demand_score, margin_score, competition_score,
            supplier_score, shipping_score, gross_margin,
            candidate, is_viable, rejection_reasons,
        )

        score_breakdown = {
            "weights": self.WEIGHTS,
            "components": {
                "demand":      {"score": round(demand_score, 1),      "weight": self.WEIGHTS["demand"],      "contribution": round(demand_score * self.WEIGHTS["demand"], 1)},
                "margin":      {"score": round(margin_score, 1),      "weight": self.WEIGHTS["margin"],      "contribution": round(margin_score * self.WEIGHTS["margin"], 1)},
                "competition": {"score": round(competition_score, 1), "weight": self.WEIGHTS["competition"], "contribution": round(competition_score * self.WEIGHTS["competition"], 1)},
                "supplier":    {"score": round(supplier_score, 1),    "weight": self.WEIGHTS["supplier"],    "contribution": round(supplier_score * self.WEIGHTS["supplier"], 1)},
                "shipping":    {"score": round(shipping_score, 1),    "weight": self.WEIGHTS["shipping"],    "contribution": round(shipping_score * self.WEIGHTS["shipping"], 1)},
            },
        }

        return ScoreResult(
            opportunity_score=round(opportunity_score, 1),
            confidence_score=round(confidence_score, 1),
            risk_score=round(risk_score, 1),
            demand_score=round(demand_score, 1),
            margin_score=round(margin_score, 1),
            competition_score=round(competition_score, 1),
            supplier_score=round(supplier_score, 1),
            shipping_score=round(shipping_score, 1),
            gross_margin=round(gross_margin, 4),
            estimated_selling_price=candidate.estimated_selling_price,
            supplier_cost=candidate.supplier_cost,
            shipping_cost=candidate.shipping_cost,
            profit_per_unit=round(profit_per_unit, 2),
            is_viable=is_viable,
            rejection_reasons=rejection_reasons,
            recommendation=recommendation,
            explanation=explanation,
            score_breakdown=score_breakdown,
        )

    def _calc_demand(self, c: ProductCandidate) -> float:
        scores = [
            c.trend_score,
            c.search_volume_score,
            c.social_signal_score,
            c.sales_velocity_score,
        ]
        active = [s for s in scores if s > 0]
        return sum(active) / len(active) if active else 0.0

    def _calc_margin(self, gross_margin: float) -> float:
        if gross_margin >= 0.70: return 100.0
        if gross_margin >= 0.60: return 90.0
        if gross_margin >= 0.50: return 75.0
        if gross_margin >= 0.45: return 60.0
        if gross_margin >= 0.40: return 45.0
        if gross_margin >= 0.30: return 20.0
        return 0.0

    def _calc_competition(self, c: ProductCandidate) -> float:
        scores = [c.competition_score]
        if c.market_saturation > 0:
            scores.append(100 - c.market_saturation)
        return sum(scores) / len(scores)

    def _calc_supplier(self, c: ProductCandidate) -> float:
        scores = []
        if c.supplier_rating > 0:
            scores.append((c.supplier_rating / 5.0) * 100)
        if c.supplier_delivery_score > 0:
            scores.append(c.supplier_delivery_score)
        if c.supplier_inventory_score > 0:
            scores.append(c.supplier_inventory_score)
        return sum(scores) / len(scores) if scores else 50.0

    def _calc_shipping(self, c: ProductCandidate) -> float:
        if c.shipping_days <= 5:  return 100.0
        if c.shipping_days <= 7:  return 90.0
        if c.shipping_days <= 10: return 75.0
        if c.shipping_days <= 14: return 55.0
        if c.shipping_days <= 20: return 30.0
        return 10.0

    def _calc_confidence(self, c: ProductCandidate) -> float:
        score = 50.0
        # More data sources = higher confidence
        score += min(c.data_sources_count * 8, 25)
        # Fresh data
        if c.data_freshness_days <= 1:  score += 15
        elif c.data_freshness_days <= 3:  score += 10
        elif c.data_freshness_days <= 7:  score += 5
        # Trend consistency
        score += c.trend_consistency_score * 0.1
        return min(score, 100.0)

    def _calc_risk(self, c: ProductCandidate, gross_margin: float) -> float:
        risk = 0.0
        # Low margin = high risk
        if gross_margin < 0.45: risk += 25
        elif gross_margin < 0.50: risk += 10
        # Long shipping = higher refund risk
        if c.shipping_days > 20: risk += 30
        elif c.shipping_days > 14: risk += 15
        # Low supplier rating
        if c.supplier_rating > 0 and c.supplier_rating < 4.5: risk += 15
        # Market saturation
        if c.market_saturation > 70: risk += 20
        elif c.market_saturation > 50: risk += 10
        return min(risk, 100.0)

    def _recommend(self, score: float, viable: bool, rejections: List[str]) -> str:
        if not viable:
            return "REJECT"
        if score >= 80: return "STRONG_BUY"
        if score >= 70: return "BUY"
        if score >= 60: return "WATCH"
        return "PASS"

    def _explain(self, opp, conf, risk, demand, margin, comp, supplier, ship,
                 gross_margin, c, viable, rejections) -> str:
        if not viable:
            return f"Product rejected. Reasons: {'; '.join(rejections)}"

        parts = [f"Opportunity Score: {opp:.0f}/100 | Confidence: {conf:.0f}/100 | Risk: {risk:.0f}/100."]
        parts.append(f"Gross margin {gross_margin:.1%} on ${c.estimated_selling_price:.2f} price.")

        if demand >= 70:   parts.append("Strong demand signals detected.")
        elif demand >= 50: parts.append("Moderate demand signals.")
        else:              parts.append("Weak demand — monitor closely.")

        if comp >= 70:   parts.append("Low competition — favorable market entry.")
        elif comp >= 50: parts.append("Moderate competition.")
        else:            parts.append("High competition — differentiation required.")

        if ship >= 75: parts.append(f"Fast shipping ({c.shipping_days}d) supports customer satisfaction.")
        elif ship < 55: parts.append(f"Slow shipping ({c.shipping_days}d) is a risk factor.")

        return " ".join(parts)


# ── Singleton ─────────────────────────────────────────────────────────────────
opportunity_scorer = OpportunityScorer()
