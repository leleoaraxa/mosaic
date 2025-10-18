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


-- 1) Cadastro / Perfil
COMMENT ON MATERIALIZED VIEW view_fiis_info IS 'Informações cadastrais completas de cada Fundo Imobiliário listado na B3 (1 linha por fundo).||ask:intents=cadastro;keywords=cadastro,ficha,perfil,cnpj,site,administrador,custodiante,gestor,tipo,segmento,classificação,publico-alvo,ipo,isin,b3;synonyms.cadastro=cadastro,perfil,ficha,informações,cnpj,administrador,gestor,custodiante,site,tipo,segmento,classificação,público-alvo,ipo,isin,nome b3,valor de mercado,p/vp,market cap,sharpe,volatilidade,dividend payout,cap rate,ev,eps,rps,equity per share,revenue per share;latest_words=último,últimos,mais recente,recente,atual;timewords=hoje,ontem,janeiro,fevereiro,março,abril,maio,junho,julho,agosto,setembro,outubro,novembro,dezembro;weights.keywords=1;weights.synonyms=2;';
-- 2) Dividendos (histórico / últimos)
COMMENT ON MATERIALIZED VIEW view_fiis_history_dividends IS 'Histórico detalhado de dividendos distribuídos por cada FII, incluindo datas de pagamento e valores declarados.||ask:intents=dividends,historico;keywords=dividendo,dividendos,rendimentos,rendimento,provento,proventos,histórico,último,mais recente,yield,dy,repasse;synonyms.dividends=dividendo,dividendos,rendimentos,proventos,pagamentos,repasse,yield,dy;synonyms.historico=histórico,histórico de dividendos,mês a mês,anual,total,linha do tempo;latest_words=último,últimos,mais recente,recente,atual;timewords=hoje,ontem,mes passado,mês anterior,ano atual,12 meses,janeiro,fevereiro,março,abril,maio,junho,julho,agosto,setembro,outubro,novembro,dezembro;weights.keywords=1;weights.synonyms=2;';
-- 3) Ativos / Imóveis (portfólio)
COMMENT ON MATERIALIZED VIEW view_fiis_history_assets IS 'Relação completa dos ativos e imóveis integrantes do portfólio de cada FII, com localização e características principais.||ask:intents=ativos,imoveis;keywords=imóvel,imoveis,ativo,ativos,asset,endereço,localização,portfólio,propriedade,shopping,galpão,cri,papel;synonyms.ativos=imóveis,ativos,bens,propriedades,portfólio,empreendimentos,galpões,shoppings,lojas,crIs,papéis;weights.keywords=1;weights.synonyms=2;';
-- 4) Processos judiciais
COMMENT ON MATERIALIZED VIEW view_fiis_history_judicial IS 'Processos judiciais e ações legais associadas a cada Fundo Imobiliário, incluindo número do processo, valor da causa e status da instância.||ask:intents=judicial,processos;keywords=judicial,processo,ação,instância,valor da causa,riscos,litígio,decisão,cível,trabalhista,administrativo,cvm;synonyms.judicial=processo,ação,litígio,demanda,causa,processos administrativos,cvm,trabalhista,cível;weights.keywords=1;weights.synonyms=2;';
-- 5) Preços (série temporal / último)
COMMENT ON MATERIALIZED VIEW view_fiis_history_prices IS 'Série temporal de preços dos FIIs, contemplando valores de abertura, fechamento, máxima e mínima.||ask:intents=precos,historico;keywords=preço,preços,fechamento,abertura,alta,baixa,histórico,gráfico,cotação,cota,média móvel,tendência;synonyms.precos=preço,cotação,valor,fechamento,cota,última cotação,atual,ontem,hoje;synonyms.historico=histórico,evolução de preços,série temporal,gráfico;latest_words=último,últimos,mais recente,recente,atual;timewords=hoje,ontem,mes passado,mês anterior,ano atual,30 dias,janeiro,fevereiro,março,abril,maio,junho,julho,agosto,setembro,outubro,novembro,dezembro;weights.keywords=1;weights.synonyms=2;';
-- 6) Notícias (últimas / histórico)
COMMENT ON MATERIALIZED VIEW view_fiis_history_news IS 'Notícias e publicações relacionadas aos Fundos Imobiliários, agregadas por fonte e data de divulgação.||ask:intents=noticias,news;keywords=notícia,notícias,news,título,fonte,matéria,divulgação,publicação,manchete;synonyms.noticias=notícia,notícias,news,manchete,publicação,divulgação,comunicado,fato relevante;latest_words=último,últimos,mais recente,recente,atual;timewords=hoje,ontem,semana,mês,janeiro,fevereiro,março,abril,maio,junho,julho,agosto,setembro,outubro,novembro,dezembro;weights.keywords=1;weights.synonyms=2;';
-- 7) Indicadores de mercado (índices, taxas-índice)
COMMENT ON MATERIALIZED VIEW view_market_indicators IS 'Indicadores e índices de mercado relevantes para o universo de FIIs, como IFIX, CDI, SELIC, dólar e euro.||ask:intents=indicadores,mercado;keywords=ifix,ifil,ibov,cdi,selic,dólar,euro,indicadores,benchmark,referência,ipca,igpm,incc;synonyms.indicadores=indicadores,índices,taxas,benchmarks,ipca,igpm,incc,inflação;latest_words=último,mais recente,atual;timewords=hoje,ontem,acumulado,12 meses,ano,2024,2025,janeiro,...,dezembro;weights.keywords=1;weights.synonyms=2;';
-- 8) Taxas/índices econômicos diários (séries)
COMMENT ON MATERIALIZED VIEW view_history_taxes IS 'Séries históricas de taxas financeiras e índices econômicos diários, incluindo CDI, SELIC e poupança.||ask:intents=taxas,diario;keywords=cdi,selic,poupança,juros,índices,diário,ipca,igpm,incc;synonyms.taxas=taxas,juros,índices,indicadores,diário,diaria;latest_words=último,mais recente,atual;timewords=hoje,ontem,acumulado,no ano,12 meses,janeiro,...,dezembro;weights.keywords=1;weights.synonyms=2;';



COMMENT ON COLUMN view_fiis_info.ticker IS 'Código do fundo na B3.|Código FII';
COMMENT ON COLUMN view_fiis_info.fii_cnpj IS 'CNPJ do FII (identificador único).|CNPJ';
COMMENT ON COLUMN view_fiis_info.ticker_full_name IS 'Nome completo do ticker.|Nome completo';
COMMENT ON COLUMN view_fiis_info.b3_name IS 'Nome de pregão na B3.|Nome B3';
COMMENT ON COLUMN view_fiis_info.classification IS 'Classificação oficial do fundo.|Classificação';
COMMENT ON COLUMN view_fiis_info.sector IS 'Setor de atuação do fundo.|Setor';
COMMENT ON COLUMN view_fiis_info.sub_sector IS 'Tipo de indústria.|Tipo de indústria';
COMMENT ON COLUMN view_fiis_info.management_type IS 'Tipo de gestão (ativa/passiva).|Tipo de gestão';
COMMENT ON COLUMN view_fiis_info.target_market IS 'Público alvo.|Público alvo';
COMMENT ON COLUMN view_fiis_info.is_exclusive IS 'Indica se o fundo é exclusivo (boolean).|Fundo exclusivo';
COMMENT ON COLUMN view_fiis_info.isin IS 'Código ISIN do fundo.|Código ISIN';
COMMENT ON COLUMN view_fiis_info.ipo_date IS 'Data do IPO do fundo.|Data IPO';
COMMENT ON COLUMN view_fiis_info.website_url IS 'URL oficial do fundo.|Site oficial';
COMMENT ON COLUMN view_fiis_info.admin_name IS 'Nome do administrador do fundo.|Administrador';
COMMENT ON COLUMN view_fiis_info.admin_cnpj IS 'CNPJ do administrador.|CNPJ administrador';
COMMENT ON COLUMN view_fiis_info.custodian_name IS 'Nome do custodiante do fundo.|Custodiante';
COMMENT ON COLUMN view_fiis_info.ifil_weight_pct IS 'Participação percentual no IFIL.|Participação IFIL';
COMMENT ON COLUMN view_fiis_info.ifix_weight_pct IS 'Participação percentual no IFIX.|Participação IFIX';
COMMENT ON COLUMN view_fiis_info.dy_monthly_pct IS 'Dividend yield mensal.|DY mensal';
COMMENT ON COLUMN view_fiis_info.dy_pct IS 'Dividend yield anual.|DY anual';
COMMENT ON COLUMN view_fiis_info.sum_anual_dy_amt IS 'Soma dos dividendos pagos por cota no último ano.|Dividendos anuais';
COMMENT ON COLUMN view_fiis_info.last_dividend_amt IS 'Último dividendo pago por cota.|Último dividendo';
COMMENT ON COLUMN view_fiis_info.last_payment_date IS 'Data do último pagamento de dividendo.|Data pagamento';
COMMENT ON COLUMN view_fiis_info.market_cap_value IS 'Valor de mercado do fundo.|Valor de mercado';
COMMENT ON COLUMN view_fiis_info.enterprise_value IS 'Enterprise value (valor da firma).|Valor da firma';
COMMENT ON COLUMN view_fiis_info.price_book_ratio IS 'Índice Preço/Patrimônio.|P/VP';
COMMENT ON COLUMN view_fiis_info.equity_per_share IS 'Patrimônio líquido por cota.|VPA';
COMMENT ON COLUMN view_fiis_info.revenue_per_share IS 'Receita por cota.|Receita por cota';
COMMENT ON COLUMN view_fiis_info.dividend_payout_pct IS 'Payout ratio em percentual.|Dividend Payout';
COMMENT ON COLUMN view_fiis_info.growth_rate IS 'Taxa de crescimento percentual.|Crescimento do patrimônio';
COMMENT ON COLUMN view_fiis_info.cap_rate IS 'Cap rate percentual.|Taxa de capitalização';
COMMENT ON COLUMN view_fiis_info.volatility_ratio IS 'Volatilidade percentual.|Volatilidade';
COMMENT ON COLUMN view_fiis_info.sharpe_ratio IS 'Índice de Sharpe.|Sharpe';
COMMENT ON COLUMN view_fiis_info.treynor_ratio IS 'Índice de Treynor.|Treynor';
COMMENT ON COLUMN view_fiis_info.jensen_alpha IS 'Alfa de Jensen.|Jensen';
COMMENT ON COLUMN view_fiis_info.beta_index IS 'Índice beta.|Beta';
COMMENT ON COLUMN view_fiis_info.leverage_ratio IS 'Índice de alavancagem.|Alavancagem';
COMMENT ON COLUMN view_fiis_info.equity_value IS 'Patrimônio líquido total.|PL Total';
COMMENT ON COLUMN view_fiis_info.shares_count IS 'Quantidade de cotas emitidas.|Cotas emitidas';
COMMENT ON COLUMN view_fiis_info.variation_year_ratio IS 'Variação efetiva no ano (%).|YTD';
COMMENT ON COLUMN view_fiis_info.variation_month_ratio IS 'Variação efetiva no mês (%).|MTD';
COMMENT ON COLUMN view_fiis_info.equity_month_ratio IS 'Variação patrimonial mensal (%).|PL mês';
COMMENT ON COLUMN view_fiis_info.shareholders_count IS 'Número de cotistas.|Cotistas';
COMMENT ON COLUMN view_fiis_info.dividend_reserve_amt IS 'Reserva de dividendos.|Reserva de dividendos';
COMMENT ON COLUMN view_fiis_info.admin_fee_due_amt IS 'Taxa de administração a pagar.|Administração devida';
COMMENT ON COLUMN view_fiis_info.perf_fee_due_amt IS 'Taxa de performance a pagar.|Performance devida';
COMMENT ON COLUMN view_fiis_info.total_cash_amt IS 'Valor total em caixa.|Disponibilidades';
COMMENT ON COLUMN view_fiis_info.expected_revenue_amt IS 'Receita esperada.|Projeção receita';
COMMENT ON COLUMN view_fiis_info.liabilities_total_amt IS 'Total de passivos.|Passivos';
COMMENT ON COLUMN view_fiis_info.revenue_due_0_3m_pct IS 'Receita a vencer em até 3 meses (%).|Receita curto prazo';
COMMENT ON COLUMN view_fiis_info.revenue_due_3_6m_pct IS 'Receita a vencer em 3 a 6 meses (%).|Vencimento receita 3-6m';
COMMENT ON COLUMN view_fiis_info.revenue_due_6_9m_pct IS 'Receita a vencer em 6 a 9 meses (%).|Vencimento receita 6-9m';
COMMENT ON COLUMN view_fiis_info.revenue_due_9_12m_pct IS 'Receita a vencer em 9 a 12 meses (%).|Vencimento receita 9-12m';
COMMENT ON COLUMN view_fiis_info.revenue_due_12_15m_pct IS 'Receita a vencer em 12 a 15 meses (%).|Vencimento receita 12-15m';
COMMENT ON COLUMN view_fiis_info.revenue_due_15_18m_pct IS 'Receita a vencer em 15 a 18 meses (%).|Vencimento receita 15-18m';
COMMENT ON COLUMN view_fiis_info.revenue_due_18_21m_pct IS 'Receita a vencer em 18 a 21 meses (%).|Vencimento receita 18-21m';
COMMENT ON COLUMN view_fiis_info.revenue_due_21_24m_pct IS 'Receita a vencer em 21 a 24 meses (%).|Vencimento receita 21-24m';
COMMENT ON COLUMN view_fiis_info.revenue_due_24_27m_pct IS 'Receita a vencer em 24 a 27 meses (%).|Vencimento receita 24-27m';
COMMENT ON COLUMN view_fiis_info.revenue_due_27_30m_pct IS 'Receita a vencer em 27 a 30 meses (%).|Vencimento receita 27-30m';
COMMENT ON COLUMN view_fiis_info.revenue_due_30_33m_pct IS 'Receita a vencer em 30 a 33 meses (%).|Vencimento receita 30-33m';
COMMENT ON COLUMN view_fiis_info.revenue_due_33_36m_pct IS 'Receita a vencer em 33 a 36 meses (%).|Vencimento receita 33-36m';
COMMENT ON COLUMN view_fiis_info.revenue_due_over_36m_pct IS 'Receita a vencer acima de 36 meses (%).|Receita longo prazo';
COMMENT ON COLUMN view_fiis_info.revenue_due_undetermined_pct IS 'Receita a vencer sem prazo definido (%).|Receita sem prazo';
COMMENT ON COLUMN view_fiis_info.revenue_igpm_pct IS 'Receita indexada ao IGP-M (%).|Receita indexada IGP-M';
COMMENT ON COLUMN view_fiis_info.revenue_inpc_pct IS 'Receita indexada ao INPC (%).|Receita indexada INPC';
COMMENT ON COLUMN view_fiis_info.revenue_ipca_pct IS 'Receita indexada ao IPCA (%).|Receita indexada IPCA';
COMMENT ON COLUMN view_fiis_info.revenue_incc_pct IS 'Receita indexada ao INCC (%).|Receita indexada INCC';
COMMENT ON COLUMN view_fiis_info.users_ranking_count IS 'Ranking atribuído por usuários.|Ranking usuários';
COMMENT ON COLUMN view_fiis_info.users_rank_movement_count IS 'Movimento do ranking de usuários.|Movimento usuários';
COMMENT ON COLUMN view_fiis_info.sirios_ranking_count IS 'Ranking atribuído pelo sistema Sirios.|Ranking Sirios';
COMMENT ON COLUMN view_fiis_info.sirios_rank_movement_count IS 'Movimento do ranking Sirios.|Movimento Sirios';
COMMENT ON COLUMN view_fiis_info.ifix_ranking_count IS 'Ranking relativo ao índice IFIX.|Ranking IFIX';
COMMENT ON COLUMN view_fiis_info.ifix_rank_movement_count IS 'Movimento de posição no IFIX.|Movimento IFIX';
COMMENT ON COLUMN view_fiis_info.ifil_ranking_count IS 'Ranking relativo ao índice IFIL.|Ranking IFIL';
COMMENT ON COLUMN view_fiis_info.ifil_rank_movement_count IS 'Movimento de posição no IFIL.|Movimento IFIL';
COMMENT ON COLUMN view_fiis_info.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_info.updated_at IS 'Data da última atualização do registro.|Atualizado em';




COMMENT ON COLUMN view_fiis_history_dividends.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_dividends.traded_until_date IS 'Data limite de negociação com direito ao dividendo.|Data limite de negociação';
COMMENT ON COLUMN view_fiis_history_dividends.payment_date IS 'Data de pagamento do dividendo.|Data de pagamento';
COMMENT ON COLUMN view_fiis_history_dividends.dividend_amt IS 'Valor do dividendo pago.|Valor do dividendo';
COMMENT ON COLUMN view_fiis_history_dividends.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_dividends.updated_at IS 'Data da última atualização do registro.|Atualizado em';

COMMENT ON COLUMN view_fiis_history_assets.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_assets.asset_name IS 'Nome do ativo (imóvel).|Nome do ativo';
COMMENT ON COLUMN view_fiis_history_assets.asset_class IS 'Classe de ativo.|Classe';
COMMENT ON COLUMN view_fiis_history_assets.asset_address IS 'Endereço do ativo.|Endereço';
COMMENT ON COLUMN view_fiis_history_assets.total_area IS 'Área total do ativo em m².|Área total';
COMMENT ON COLUMN view_fiis_history_assets.units_count IS 'Número de unidades do ativo.|Unidades';
COMMENT ON COLUMN view_fiis_history_assets.vacancy_ratio IS 'Taxa de vacância do ativo (%).|Vacância';
COMMENT ON COLUMN view_fiis_history_assets.non_compliant_ratio IS 'Taxa de inadimplência do ativo (%).|Inadimplência';
COMMENT ON COLUMN view_fiis_history_assets.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_assets.updated_at IS 'Data da última atualização do registro.|Atualizado em';

COMMENT ON COLUMN view_fiis_history_judicial.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_judicial.process_number IS 'Número do processo judicial.|Identificador do processo';
COMMENT ON COLUMN view_fiis_history_judicial.judgment IS 'Local ou instância do julgamento.|Órgão julgador';
COMMENT ON COLUMN view_fiis_history_judicial.instance IS 'Instância judicial (ex.: 1ª, 2ª).|Instância';
COMMENT ON COLUMN view_fiis_history_judicial.initiation_date IS 'Data de abertura do processo.|Abertura';
COMMENT ON COLUMN view_fiis_history_judicial.cause_amt IS 'Valor da causa.|Montante em disputa';
COMMENT ON COLUMN view_fiis_history_judicial.process_parts IS 'Partes envolvidas no processo.|Partes';
COMMENT ON COLUMN view_fiis_history_judicial.loss_risk_pct IS 'Probabilidade de perda (%).|Risco de perda';
COMMENT ON COLUMN view_fiis_history_judicial.main_facts IS 'Fatos principais do processo.|Fatos principais';
COMMENT ON COLUMN view_fiis_history_judicial.loss_impact_analysis IS 'Análise do impacto em caso de perda.|Análise de impacto';
COMMENT ON COLUMN view_fiis_history_judicial.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_judicial.updated_at IS 'Data da última atualização do registro.|Atualizado em';


COMMENT ON COLUMN view_fiis_history_prices.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_prices.price_date IS 'Data de referência do preço.|Data de referência';
COMMENT ON COLUMN view_fiis_history_prices.close_price IS 'Preço de fechamento.|Fechamento';
COMMENT ON COLUMN view_fiis_history_prices.adj_close_price IS 'Preço de fechamento ajustado.|Preço ajustado';
COMMENT ON COLUMN view_fiis_history_prices.open_price IS 'Preço de abertura.|Abertura';
COMMENT ON COLUMN view_fiis_history_prices.daily_range_pct IS 'Variação diária de preço.|Variação do dia';
COMMENT ON COLUMN view_fiis_history_prices.max_price IS 'Preço máximo no dia.|Máxima';
COMMENT ON COLUMN view_fiis_history_prices.min_price IS 'Preço mínimo no dia.|Mínima';
COMMENT ON COLUMN view_fiis_history_prices.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_prices.updated_at IS 'Data da última atualização do registro.|Atualizado em';


COMMENT ON COLUMN view_fiis_history_news.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_news.news_url IS 'URL da notícia.|Link da notícia';
COMMENT ON COLUMN view_fiis_history_news.news_source IS 'Fonte do conteúdo da notícia.|Origem';
COMMENT ON COLUMN view_fiis_history_news.news_title IS 'Título da notícia.|Título';
COMMENT ON COLUMN view_fiis_history_news.news_date IS 'Data da notícia.|Data';
COMMENT ON COLUMN view_fiis_history_news.news_tags IS 'Tags relacionadas à notícia.|Tags';
COMMENT ON COLUMN view_fiis_history_news.news_description IS 'Resumo ou descrição da notícia.|Resumo';
COMMENT ON COLUMN view_fiis_history_news.news_image_url IS 'URL da imagem da notícia.|Link da imagem da notícia';
COMMENT ON COLUMN view_fiis_history_news.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_news.updated_at IS 'Data da última atualização do registro.|Atualizado em';



COMMENT ON COLUMN view_market_indicators.indicator_date IS 'Data de referência do indicador.|Data';
COMMENT ON COLUMN view_market_indicators.indicator_name IS 'Nome ou identificador do indicador.|Indicador';
COMMENT ON COLUMN view_market_indicators.indicator_amt IS 'Valor registrado do indicador.|Valor';
COMMENT ON COLUMN view_market_indicators.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_market_indicators.updated_at IS 'Data da última atualização do registro.|Atualizado em';

COMMENT ON COLUMN view_history_taxes.tax_date IS 'Data de referência.|Data';
COMMENT ON COLUMN view_history_taxes.cdi_rate_pct IS 'Taxa CDI (%).|CDI';
COMMENT ON COLUMN view_history_taxes.selic_rate_pct IS 'Taxa SELIC (%).|SELIC';
COMMENT ON COLUMN view_history_taxes.ibov_points_count IS 'Pontuação do índice IBOVESPA.|Pontuação IBOVESPA';
COMMENT ON COLUMN view_history_taxes.ibov_var_pct IS 'Variação percentual do IBOVESPA.|Variação IBOVESPA';
COMMENT ON COLUMN view_history_taxes.ifix_points_count IS 'Pontuação do índice IFIX.|Pontuação IFIX';
COMMENT ON COLUMN view_history_taxes.ifix_var_pct IS 'Variação percentual do IFIX.|Variação IFIX';
COMMENT ON COLUMN view_history_taxes.ifil_points_count IS 'Pontuação do índice IFIL.|Pontuação IFIL';
COMMENT ON COLUMN view_history_taxes.ifil_var_pct IS 'Variação percentual do IFIL.|Variação IFIL';
COMMENT ON COLUMN view_history_taxes.usd_buy_amt IS 'Cotação de compra do dólar.|USD compra';
COMMENT ON COLUMN view_history_taxes.usd_sell_amt IS 'Cotação de venda do dólar.|USD venda';
COMMENT ON COLUMN view_history_taxes.usd_var_pct IS 'Variação percentual do dólar.|USD variação';
COMMENT ON COLUMN view_history_taxes.eur_buy_amt IS 'Cotação de compra do euro.|EURO compra';
COMMENT ON COLUMN view_history_taxes.eur_sell_amt IS 'Cotação de venda do euro.|EURO venda';
COMMENT ON COLUMN view_history_taxes.eur_var_pct IS 'Variação percentual do euro.|EURO variação';
COMMENT ON COLUMN view_history_taxes.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_history_taxes.updated_at IS 'Data da última atualização do registro.|Atualizado em';
