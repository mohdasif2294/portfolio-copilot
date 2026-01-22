"""Tests for fundamental analysis agent."""

from src.agents.tools.symbol_tools import extract_symbol
from src.agents.workflows.fundamental_analysis import (
    FundamentalScore,
    analyze_fundamentals,
)
from src.data.scrapers.screener import FundamentalData


class TestFundamentalScore:
    """Test FundamentalScore dataclass."""

    def test_total_score_calculation(self):
        """Test that total_score correctly sums all category scores."""
        score = FundamentalScore(
            valuation_score=2,
            profitability_score=1,
            growth_score=0,
            financial_health_score=-1,
            promoter_score=1,
        )
        assert score.total_score == 3  # 2+1+0-1+1 = 3

    def test_total_score_max(self):
        """Test maximum possible score."""
        score = FundamentalScore(
            valuation_score=2,
            profitability_score=2,
            growth_score=2,
            financial_health_score=2,
            promoter_score=2,
        )
        assert score.total_score == 10

    def test_total_score_min(self):
        """Test minimum possible score."""
        score = FundamentalScore(
            valuation_score=-2,
            profitability_score=-2,
            growth_score=-2,
            financial_health_score=-2,
            promoter_score=-2,
        )
        assert score.total_score == -10

    def test_recommendation_strong_buy(self):
        """Test STRONG BUY recommendation for high scores."""
        score = FundamentalScore(
            valuation_score=2,
            profitability_score=2,
            growth_score=1,
            financial_health_score=1,
            promoter_score=0,
        )
        assert score.total_score == 6
        assert score.recommendation == "STRONG BUY"

    def test_recommendation_buy(self):
        """Test BUY recommendation for medium-high scores."""
        score = FundamentalScore(
            valuation_score=1,
            profitability_score=1,
            growth_score=0,
            financial_health_score=0,
            promoter_score=1,
        )
        assert score.total_score == 3
        assert score.recommendation == "BUY"

    def test_recommendation_hold(self):
        """Test HOLD recommendation for neutral scores."""
        score = FundamentalScore(
            valuation_score=0,
            profitability_score=0,
            growth_score=0,
            financial_health_score=0,
            promoter_score=0,
        )
        assert score.total_score == 0
        assert score.recommendation == "HOLD"

    def test_recommendation_sell(self):
        """Test SELL recommendation for negative scores."""
        score = FundamentalScore(
            valuation_score=-1,
            profitability_score=-1,
            growth_score=-1,
            financial_health_score=0,
            promoter_score=0,
        )
        assert score.total_score == -3
        assert score.recommendation == "SELL"

    def test_recommendation_strong_sell(self):
        """Test STRONG SELL recommendation for very negative scores."""
        score = FundamentalScore(
            valuation_score=-2,
            profitability_score=-2,
            growth_score=-1,
            financial_health_score=-1,
            promoter_score=0,
        )
        assert score.total_score == -6
        assert score.recommendation == "STRONG SELL"


class TestAnalyzeFundamentals:
    """Test the analyze_fundamentals scoring function."""

    def test_excellent_stock(self):
        """Test scoring for a stock with excellent fundamentals."""
        data = FundamentalData(
            symbol="TCS",
            name="Tata Consultancy Services",
            pe_ratio=25,  # Good P/E
            pb_ratio=10,  # Average P/B
            dividend_yield=1.5,  # Decent yield
            roe=40,  # Excellent ROE
            roce=45,  # Excellent ROCE
            revenue_growth_3yr=12,  # Good growth
            profit_growth_3yr=15,  # Good growth
            debt_to_equity=0.1,  # Very low debt
            current_ratio=2.5,  # Strong current ratio
            promoter_holding=72,  # High promoter holding
            promoter_holding_change=0.5,  # Increasing
        )
        score = analyze_fundamentals(data)
        assert score.total_score >= 5  # Should be STRONG BUY
        assert score.recommendation == "STRONG BUY"

    def test_poor_stock(self):
        """Test scoring for a stock with poor fundamentals."""
        data = FundamentalData(
            symbol="BAD",
            name="Bad Company",
            pe_ratio=60,  # Very high P/E
            pb_ratio=8,  # High P/B
            dividend_yield=0,  # No dividend
            roe=5,  # Low ROE
            roce=6,  # Low ROCE
            revenue_growth_3yr=2,  # Low growth
            profit_growth_3yr=-5,  # Negative growth
            debt_to_equity=3.0,  # High debt
            current_ratio=0.8,  # Poor liquidity
            promoter_holding=20,  # Low promoter holding
            promoter_holding_change=-5,  # Decreasing significantly
        )
        score = analyze_fundamentals(data)
        assert score.total_score <= -4  # Should be SELL or worse
        assert score.recommendation in ("SELL", "STRONG SELL")

    def test_average_stock(self):
        """Test scoring for an average stock."""
        data = FundamentalData(
            symbol="AVG",
            name="Average Company",
            pe_ratio=20,  # Average P/E
            pb_ratio=3,  # Average P/B
            dividend_yield=1.0,  # Low yield
            roe=14,  # Below good threshold
            roce=12,  # Average ROCE
            revenue_growth_3yr=8,  # Average growth
            profit_growth_3yr=8,  # Average growth
            debt_to_equity=1.0,  # Moderate debt
            current_ratio=1.5,  # Acceptable
            promoter_holding=50,  # Moderate
            promoter_holding_change=0,  # Stable
        )
        score = analyze_fundamentals(data)
        assert -1 <= score.total_score <= 4  # Should be around HOLD to BUY
        assert score.recommendation in ("HOLD", "BUY")


class TestExtractSymbol:
    """Test symbol extraction from queries."""

    def test_extract_simple_query(self):
        """Test extracting symbol from simple queries."""
        assert extract_symbol("Is TCS a good buy?") == "TCS"
        assert extract_symbol("Tell me about RELIANCE") == "RELIANCE"
        assert extract_symbol("Fundamentals of HDFCBANK") == "HDFCBANK"

    def test_extract_lowercase(self):
        """Test that extraction works with lowercase."""
        result = extract_symbol("is reliance a good buy?")
        assert result.upper() == "RELIANCE"

    def test_extract_with_nse_prefix(self):
        """Test extraction with NSE: prefix."""
        assert extract_symbol("What about NSE:INFY?") == "INFY"

    def test_extract_complex_query(self):
        """Test extraction from complex queries."""
        # extract_symbol may return mapped symbols
        result = extract_symbol("Should I buy Infosys stock?")
        # INFY is the NSE symbol for Infosys
        assert result.upper() in ("INFOSYS", "INFY")


class TestScoreNotes:
    """Test that score notes are generated correctly."""

    def test_valuation_notes(self):
        """Test valuation notes are generated."""
        data = FundamentalData(
            symbol="TEST", pe_ratio=10, pb_ratio=1.5, dividend_yield=3
        )
        score = analyze_fundamentals(data)
        assert len(score.valuation_notes) > 0

    def test_profitability_notes(self):
        """Test profitability notes are generated."""
        data = FundamentalData(symbol="TEST", roe=25, roce=20)
        score = analyze_fundamentals(data)
        assert len(score.profitability_notes) > 0

    def test_financial_health_notes(self):
        """Test financial health notes are generated."""
        data = FundamentalData(symbol="TEST", debt_to_equity=0.2, current_ratio=3)
        score = analyze_fundamentals(data)
        assert len(score.financial_health_notes) > 0
