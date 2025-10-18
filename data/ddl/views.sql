CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION public.unaccent_ci(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT public.unaccent('public.unaccent', lower($1))
$$;

-- =====================================================================
-- VIEW: view_fiis_info
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_info CASCADE;

CREATE MATERIALIZED VIEW view_fiis_info AS
SELECT
    bt.ticker AS ticker,
    bt.document AS fii_cnpj,
    bt.ticker_name AS ticker_full_name,
    bt.bovespa_name AS b3_name,
    INITCAP(bt.classification) AS classification,
    bt.sector AS sector,
    bt.industry_type AS sub_sector,
    bt.management_type AS management_type,
    INITCAP(bt.target_market) AS target_market,
    CASE
        WHEN bt.exclusive_fund = 'S' THEN true
        WHEN bt.exclusive_fund = 'N' THEN false
        ELSE NULL
    END AS is_exclusive,
    bt.isin_code AS isin,
    TO_CHAR(TO_DATE(bt.ipo_date, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS ipo_date,
    bt.website AS website_url,
    INITCAP(bt.administrator_name) AS admin_name,
    REGEXP_REPLACE(bt.administrator_document, '(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})', '\1.\2.\3/\4-\5') AS admin_cnpj,
    INITCAP(bt.custodian_name) AS custodian_name,
    COALESCE(itl.percent_ifil, 0) AS ifil_weight_pct,
    COALESCE(itx.percent_ifix, 0) AS ifix_weight_pct,
    ROUND(sd.dividend_yield_m::numeric, 2) AS dy_monthly_pct,
    ROUND(sd.dividend_yield_12m::numeric, 2) AS dy_pct,
    ROUND(COALESCE(sd.dividends_sum_12m::numeric, 0), 2) AS sum_anual_dy_amt,
    ROUND(COALESCE(sd.last_dividend::numeric, 0), 2) AS last_dividend_amt,
    TO_CHAR(TO_DATE(sd.payment_date::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS last_payment_date,
    ROUND(cf.market_cap::numeric, 2) AS market_cap_value,
    ROUND(cf.enterprise_value::numeric, 2) AS enterprise_value,
    ROUND(cf.price_to_book_ratio::numeric, 4) AS price_book_ratio,
    ROUND(cf.equity_per_share::numeric, 3) AS equity_per_share,
    ROUND(cf.revenue_per_share::numeric, 3) AS revenue_per_share,
    ROUND(cf.dividend_payout_ratio::numeric, 2) AS dividend_payout_pct,
    ROUND(cf.growth_rate::numeric, 3) AS growth_rate,
    ROUND(cf.cap_rate::numeric, 3) AS cap_rate,
    ROUND(cf.volatility::numeric, 4) AS volatility_ratio,
    ROUND(cf.sharpe_ratio::numeric, 4) AS sharpe_ratio,
    ROUND(cf.treynor_ratio::numeric, 4) AS treynor_ratio,
    ROUND(cf.jensen_alpha::numeric, 3) AS jensen_alpha,
    ROUND(cf.beta_index::numeric, 3) AS beta_index,
    ROUND(cf.leverage::numeric, 4) AS leverage_ratio,
    ROUND(f.equity::numeric, 2) AS equity_value,
    ROUND(f.shares_count::numeric, 0) AS shares_count,
    ROUND(COALESCE(f.effective_variation_year, 0), 4) AS variation_year_ratio,
    CASE
        WHEN f.effective_variation_month ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.effective_variation_month, '999999999D9999'), 0), 4)
        ELSE 0
    END AS variation_month_ratio,
    CASE
        WHEN f.equity_variation_month ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.equity_variation_month, '999999999D9999'), 0), 4)
        ELSE 0
    END AS equity_month_ratio,
    CASE
        WHEN f.dividend_to_distribute ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.dividend_to_distribute, '999999999999D99'), 0), 2)
        ELSE 0
    END AS shareholders_count,
    CASE
        WHEN f.shareholders_count ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.shareholders_count, '999999999999D99'), 0), 2)
        ELSE 0
    END AS dividend_reserve_amt,
    CASE
        WHEN f.administration_fee_to_pay ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.administration_fee_to_pay, '999999999999D99'), 0), 2)
        ELSE 0
    END AS admin_fee_due_amt,
    CASE
        WHEN f.performance_fee_to_pay ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.performance_fee_to_pay, '999999999999D99'), 0), 2)
        ELSE 0
    END AS perf_fee_due_amt,
    CASE
        WHEN f.total_cash ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.total_cash, '999999999999D99'), 0), 2)
        ELSE 0
    END AS total_cash_amt,
    CASE
        WHEN f.expected_revenue ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.expected_revenue, '999999999999D99'), 0), 2)
        ELSE 0
    END AS expected_revenue_amt,
    CASE
        WHEN f.total_liabilities ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.total_liabilities, '999999999999D99'), 0), 2)
        ELSE 0
    END AS liabilities_total_amt,
    CASE
        WHEN f.percent_total_revenue_due_upto3months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_upto3months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_0_3m_pct,
    CASE
        WHEN f.percent_total_revenue_due_3to6months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_3to6months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_3_6m_pct,
    CASE
        WHEN f.percent_total_revenue_due_6to9months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_6to9months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_6_9m_pct,
    CASE
        WHEN f.percent_total_revenue_due_9to12months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_9to12months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_9_12m_pct,
    CASE
        WHEN f.percent_total_revenue_due_12to15months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_12to15months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_12_15m_pct,
    CASE
        WHEN f.percent_total_revenue_due_15to18months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_15to18months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_15_18m_pct,
    CASE
        WHEN f.percent_total_revenue_due_18to21months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_18to21months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_18_21m_pct,
    CASE
        WHEN f.percent_total_revenue_due_21to24months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_21to24months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_21_24m_pct,
    CASE
        WHEN f.percent_total_revenue_due_24to27months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_24to27months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_24_27m_pct,
    CASE
        WHEN f.percent_total_revenue_due_27to30months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_27to30months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_27_30m_pct,
    CASE
        WHEN f.percent_total_revenue_due_30to33months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_30to33months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_30_33m_pct,
    CASE
        WHEN f.percent_total_revenue_due_33to36months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_33to36months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_33_36m_pct,
    CASE
        WHEN f.percent_total_revenue_due_above36months ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_above36months, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_over_36m_pct,
    CASE
        WHEN f.percent_total_revenue_due_undetermined ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_due_undetermined, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_due_undetermined_pct,
    CASE
        WHEN f.percent_total_revenue_igpm_index ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_igpm_index, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_igpm_pct,
    CASE
        WHEN f.percent_total_revenue_inpc_index ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_inpc_index, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_inpc_pct,
    CASE
        WHEN f.percent_total_revenue_ipca_index ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_ipca_index, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_ipca_pct,
    CASE
        WHEN f.percent_total_revenue_incc_index ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(f.percent_total_revenue_incc_index, '999999999D9999'), 0), 4)
        ELSE 0
    END AS revenue_incc_pct,
    ROUND(r.users_ranking::numeric, 0) AS users_ranking_count,
    ROUND(r.users_ranking_positions_moved::numeric, 0) AS users_rank_movement_count,
    ROUND(r.sirios_ranking::numeric, 0) AS sirios_ranking_count,
    ROUND(r.sirios_ranking_positions_moved::numeric, 0) AS sirios_rank_movement_count,
    ROUND(r.ifix_ranking::numeric, 0) AS ifix_ranking_count,
    ROUND(r.ifix_ranking_positions_moved::numeric, 0) AS ifix_rank_movement_count,
    ROUND(r.ifil_ranking::numeric, 0) AS ifil_ranking_count,
    ROUND(r.ifil_ranking_positions_moved::numeric, 0) AS ifil_rank_movement_count,
    TO_CHAR(TO_DATE(bt.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(bt.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM basics_tickers bt
LEFT JOIN ifil_tickers itl ON bt.ticker = itl.ticker
LEFT JOIN ifix_tickers itx ON bt.ticker = itx.ticker
LEFT JOIN dividends_tickers sd ON bt.ticker = sd.ticker
LEFT JOIN calc_financials_tickers cf ON bt.ticker = cf.ticker
LEFT JOIN financials_tickers f ON bt.ticker = f.ticker
LEFT JOIN ranking_fiis r ON bt.ticker = r.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_info_ticker ON view_fiis_info(ticker);
CREATE INDEX idx_fiis_info_fii_cnpj ON view_fiis_info(fii_cnpj);
CREATE INDEX idx_fiis_info_isin ON view_fiis_info(isin);
CREATE INDEX idx_fiis_info_admin_cnpj ON view_fiis_info(admin_cnpj);
CREATE INDEX IF NOT EXISTS idx_fiis_info_sector_unaccent ON view_fiis_info (public.unaccent_ci(sector));
CREATE INDEX IF NOT EXISTS idx_fiis_info_sub_sector_unaccent ON view_fiis_info (public.unaccent_ci(sub_sector));
CREATE INDEX IF NOT EXISTS idx_fiis_info_classification_unaccent ON view_fiis_info (public.unaccent_ci(classification));
CREATE INDEX IF NOT EXISTS idx_fiis_info_management_type_unaccent ON view_fiis_info (public.unaccent_ci(management_type));
CREATE INDEX IF NOT EXISTS idx_fiis_info_target_market_unaccent ON view_fiis_info (public.unaccent_ci(target_market));

ALTER MATERIALIZED VIEW public.view_fiis_info OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_info;

-- =====================================================================
-- VIEW: view_fiis_history_dividends
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_dividends CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_dividends AS
SELECT
    bt.ticker AS ticker,
    DATE_TRUNC('day', hd.traded_until) AS traded_until_date,
    DATE_TRUNC('day', hd.payment_date) AS payment_date,
    hd.amount AS dividend_amt,
	TO_CHAR(TO_DATE(hd.created_at::text,
		'YYYY-MM-DD'),
	    'YYYY-MM-DD HH24:MI:SS') 				AS created_at,
	TO_CHAR(TO_DATE(hd.updated_at::text,
		'YYYY-MM-DD'),
	    'YYYY-MM-DD HH24:MI:SS') 				AS updated_at
FROM basics_tickers bt
JOIN hist_dividends hd ON bt.ticker = hd.ticker
ORDER BY bt.ticker ASC, hd.traded_until DESC, hd.payment_date DESC;

CREATE UNIQUE INDEX idx_fiis_hist_dividends
    ON view_fiis_history_dividends(ticker, traded_until_date, payment_date);


ALTER MATERIALIZED VIEW public.view_fiis_history_dividends OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_dividends;

-- =====================================================================
-- VIEW: view_fiis_history_assets
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_assets CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_assets AS
SELECT
    bt.ticker AS ticker,
    at.asset AS asset_name,
    at.asset_class AS asset_class,
    at.address AS asset_address,
    CASE
        WHEN at.total_area ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(at.total_area, '999999999D9999'), 0), 2)
        ELSE 0
    END AS total_area,
    CASE
        WHEN at.number_units ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(at.number_units, '999999999D9999'), 0), 0)
        ELSE 0
    END AS units_count,
    CASE
        WHEN at.space_vacancy ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(at.space_vacancy, '999999999D9999'), 0), 4)
        ELSE 0
    END AS vacancy_ratio,
    CASE
        WHEN at.non_compliance ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(at.non_compliance, '999999999D9999'), 0), 4)
        ELSE 0
    END AS non_compliant_ratio,
    CASE
        WHEN at.asset_status = '1' THEN 'Ativo'
        WHEN at.asset_status = '0' THEN 'Inativo'
        ELSE NULL
    END AS assets_status,
    TO_CHAR(TO_DATE(at.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(at.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM basics_tickers bt
JOIN assets_tickers at ON bt.ticker = at.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_assets
    ON view_fiis_history_assets(ticker, asset_class, asset_name, asset_address, assets_status);


ALTER MATERIALIZED VIEW public.view_fiis_history_assets OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_assets;


-- =====================================================================
-- VIEW: view_fiis_history_judicial
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_judicial CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_judicial AS
SELECT
    bt.ticker          AS ticker,
    pt.process_number  AS process_number,
    pt.judgment        AS judgment,
    pt.instance        AS instance,
	TO_CHAR(TO_DATE(pt.initiation_date::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS initiation_date,
	CASE
        WHEN pt.value_of_cause ~ '^-?\d+(\.\d+)?$'
        THEN ROUND(COALESCE(TO_NUMBER(pt.value_of_cause, '999999999999D99'), 0), 2)
        ELSE 0
    END AS cause_amt,
    INITCAP(pt.process_parts)   AS process_parts,
    INITCAP(pt.chance_of_loss)  AS loss_risk_pct,
    pt.main_facts      AS main_facts,
    pt.analysis_impact_loss AS loss_impact_analysis,
    TO_CHAR(TO_DATE(pt.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(pt.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM basics_tickers bt
JOIN process_tickers pt ON bt.ticker = pt.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_judicial
    ON view_fiis_history_judicial(ticker, process_number);


ALTER MATERIALIZED VIEW public.view_fiis_history_judicial OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_judicial;

-- =====================================================================
-- VIEW: view_fiis_history_prices
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_prices CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_prices AS
SELECT
    bt.ticker          AS ticker,
	TO_CHAR(TO_DATE(p.price_ref_date::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS price_date,
    p.close_price      AS close_price,
    p.adj_close_price  AS adj_close_price,
    p.open_price       AS open_price,
	ROUND(p.daily_range::numeric, 2) AS daily_range_pct,
    p.max_price        AS max_price,
    p.min_price        AS min_price,
	TO_CHAR(TO_DATE(p.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(p.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM basics_tickers bt
JOIN price_tickers p ON bt.ticker = p.ticker
ORDER BY bt.ticker ASC, p.price_ref_date DESC;

CREATE UNIQUE INDEX idx_fiis_history_prices
    ON view_fiis_history_prices(ticker, price_date);


ALTER MATERIALIZED VIEW public.view_fiis_history_prices OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_prices;

-- =====================================================================
-- VIEW: view_fiis_history_news
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_news CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_news AS
SELECT
    bt.ticker           AS ticker,
    mn.news_topic       AS news_source,
    mn.news_title       AS news_title,
	TO_CHAR(TO_DATE(mn.news_date::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS news_date,
    mn.news_tags        AS news_tags,
    mn.news_description AS news_description,
    mn.news_url         AS news_url,
	mn.news_image		AS news_image_url,
	TO_CHAR(TO_DATE(mn.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(mn.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM basics_tickers bt
JOIN market_news mn
  ON (mn.news_title ILIKE '%' || bt.ticker || '%' OR
      mn.news_description ILIKE '%' || bt.ticker || '%')
ORDER BY bt.ticker;

CREATE UNIQUE INDEX idx_fiis_history_news
    ON view_fiis_history_news(ticker, news_url);
CREATE INDEX IF NOT EXISTS idx_news_ticker_date
ON view_fiis_history_news (ticker, news_date DESC);


ALTER MATERIALIZED VIEW public.view_fiis_history_news OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_news;


-- =====================================================================
-- VIEW: view_market_indicators
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_market_indicators CASCADE;

CREATE MATERIALIZED VIEW view_market_indicators AS
SELECT
	TO_CHAR(TO_DATE(hi.date_indicators::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS indicator_date,
    UPPER(hi.slug_indicators)   AS indicator_name,
    hi.value_indicators  AS indicator_amt,
	TO_CHAR(TO_DATE(hi.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(hi.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM public.hist_indicators hi
ORDER BY hi.date_indicators DESC, hi.slug_indicators ASC;


CREATE UNIQUE INDEX idx_market_indicators
    ON view_market_indicators(indicator_date, indicator_name);


ALTER MATERIALIZED VIEW public.view_market_indicators OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_market_indicators;

-- =====================================================================
-- VIEW: view_history_taxes
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_history_taxes CASCADE;

CREATE MATERIALIZED VIEW view_history_taxes AS
SELECT
	TO_CHAR(TO_DATE(ht.date_taxes::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS tax_date,
    ROUND(ht.cdi_taxes::numeric, 2)         AS cdi_rate_pct,
    ROUND(ht.selic_taxes::numeric, 2)       AS selic_rate_pct,
    ROUND(ht.ibovespa_taxes::numeric, 0) 	 AS ibov_points_count,
    ROUND(ht.ibovespa_variation::numeric, 2) AS ibov_var_pct,
	ROUND(ht.ifix_taxes::numeric, 0) 		 AS ifix_points_count,
    ROUND(ht.ifix_variation::numeric, 2)    AS ifix_var_pct,
	ROUND(ht.ifil_taxes::numeric, 0) 		 AS ifil_points_count,
    ROUND(ht.ifil_variation::numeric, 2)    AS ifil_var_pct,
    ROUND(ht.usd_buy::numeric, 2)           AS usd_buy_amt,
    ROUND(ht.usd_sell::numeric, 2)          AS usd_sell_amt,
    ROUND(ht.usd_variation::numeric, 2)     AS usd_var_pct,
    ROUND(ht.eur_buy::numeric, 2)           AS eur_buy_amt,
    ROUND(ht.eur_sell::numeric, 2)          AS eur_sell_amt,
    ROUND(ht.eur_variation::numeric, 2)     AS eur_var_pct,
	TO_CHAR(TO_DATE(ht.created_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS created_at,
    TO_CHAR(TO_DATE(ht.updated_at::text, 'YYYY-MM-DD'), 'YYYY-MM-DD HH24:MI:SS') AS updated_at
FROM public.hist_taxes ht
ORDER BY ht.date_taxes DESC;

CREATE UNIQUE INDEX idx_history_taxes
    ON view_history_taxes(tax_date);


ALTER MATERIALIZED VIEW public.view_history_taxes OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_history_taxes;