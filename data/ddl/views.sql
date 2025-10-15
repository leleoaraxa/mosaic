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
    bt.ticker                  				AS ticker,
	bt.document                					AS fii_cnpj,
    bt.ticker_name             				AS ticker_full_name,
    bt.bovespa_name            				AS b3_name,
    bt.classification          				AS classification,
    bt.sector                  				AS sector,
    bt.industry_type           				AS sub_sector,
    bt.management_type         				AS management_type,
    bt.target_market           				AS target_market,
    bt.exclusive_fund          				AS is_exclusive,
    bt.isin_code               				AS isin,
    bt.ipo_date                				AS ipo_date,
    bt.website                 				AS website_url,
    bt.administrator_name      				AS admin_name,
    REGEXP_REPLACE(bt.administrator_document,
        '(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})',
        '\1.\2.\3/\4-\5') 						AS admin_cnpj,
    bt.custodian_name          				AS custodian_name,
	COALESCE(itl.percent_ifil, 0)				AS ifil_weight_pct,
	COALESCE(itx.percent_ifix, 0)				AS ifix_weight_pct,
	sd.dividend_yield_m							AS dividend_yield_monthly,
	sd.dividend_yield_12m						AS dividend_yield,
	sd.dividends_sum_12m						AS sum_dividend_yearly,
    sd.last_dividend							AS last_dividend_amount,
    sd.payment_date 							AS last_dividends_payment_date,
    cf.market_cap                            	AS market_cap_value,
    cf.enterprise_value                      	AS enterprise_value,
    cf.price_to_book_ratio                   	AS price_book_ratio,
    cf.equity_per_share                      	AS equity_per_share,
    cf.revenue_per_share                     	AS revenue_per_share,
    cf.dividend_payout_ratio                 	AS payout_ratio_pct,
    cf.growth_rate                           	AS growth_rate_pct,
    cf.cap_rate                              	AS cap_rate_pct,
    cf.volatility                            	AS volatility_pct,
    cf.sharpe_ratio                          	AS sharpe_ratio,
    cf.treynor_ratio                         	AS treynor_ratio,
    cf.jensen_alpha                          	AS jensen_alpha,
    cf.beta_index                            	AS beta_index,
    cf.leverage                              	AS leverage_ratio,
    f.equity                                 	AS equity_value,
    f.shares_count                           	AS shares_count,
    f.effective_variation_year               	AS variation_year_pct,
    f.effective_variation_month              	AS variation_month_pct,
    f.equity_variation_month                 	AS equity_month_pct,
    f.shareholders_count                     	AS shareholders_count,
    f.dividend_to_distribute                 	AS dividend_reserve,
    f.administration_fee_to_pay              	AS admin_fee_due,
    f.performance_fee_to_pay                 	AS perf_fee_due,
    f.total_cash                             	AS total_cash_value,
    f.expected_revenue                       	AS expected_revenue,
    f.total_liabilities                     	AS liabilities_total,
    f.percent_total_revenue_due_upto3months  	AS revenue_due_0_3m_pct,
    f.percent_total_revenue_due_3to6months   	AS revenue_due_3_6m_pct,
    f.percent_total_revenue_due_6to9months   	AS revenue_due_6_9m_pct,
    f.percent_total_revenue_due_9to12months  	AS revenue_due_9_12m_pct,
    f.percent_total_revenue_due_12to15months 	AS revenue_due_12_15m_pct,
    f.percent_total_revenue_due_15to18months 	AS revenue_due_15_18m_pct,
    f.percent_total_revenue_due_18to21months 	AS revenue_due_18_21m_pct,
    f.percent_total_revenue_due_21to24months 	AS revenue_due_21_24m_pct,
    f.percent_total_revenue_due_24to27months 	AS revenue_due_24_27m_pct,
    f.percent_total_revenue_due_27to30months 	AS revenue_due_27_30m_pct,
    f.percent_total_revenue_due_30to33months 	AS revenue_due_30_33m_pct,
    f.percent_total_revenue_due_33to36months 	AS revenue_due_33_36m_pct,
    f.percent_total_revenue_due_above36months 	AS revenue_due_over_36m_pct,
    f.percent_total_revenue_due_undetermined  	AS revenue_due_undetermined_pct,
    f.percent_total_revenue_igpm_index       	AS revenue_igpm_pct,
    f.percent_total_revenue_inpc_index        	AS revenue_inpc_pct,
    f.percent_total_revenue_ipca_index        	AS revenue_ipca_pct,
    f.percent_total_revenue_incc_index        	AS revenue_incc_pct,
    r.users_ranking                   			AS users_ranking,
    r.users_ranking_positions_moved   			AS users_rank_movement,
    r.sirios_ranking                  			AS sirios_ranking,
    r.sirios_ranking_positions_moved  			AS sirios_rank_movement,
    r.ifix_ranking                    			AS ifix_ranking,
    r.ifix_ranking_positions_moved    			AS ifix_rank_movement,
    r.ifil_ranking                    			AS ifil_ranking,
    r.ifil_ranking_positions_moved    			AS ifil_rank_movement,
	bt.created_at              					AS created_at,
    bt.updated_at              				AS updated_at
FROM basics_tickers bt
LEFT JOIN ifil_tickers itl ON bt.ticker = itl.ticker
LEFT JOIN ifix_tickers itx ON bt.ticker= itx.ticker
LEFT JOIN dividends_tickers sd ON bt.ticker = sd.ticker
LEFT JOIN calc_financials_tickers cf ON bt.ticker = cf.ticker
LEFT JOIN financials_tickers f ON bt.ticker = f.ticker
LEFT JOIN ranking_fiis r ON bt.ticker = r.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_info_ticker ON view_fiis_info(ticker);
CREATE INDEX idx_fiis_info_fii_cnpj   ON view_fiis_info(fii_cnpj);
CREATE INDEX idx_fiis_info_isin       ON view_fiis_info(isin);
CREATE INDEX idx_fiis_info_admin_cnpj ON view_fiis_info(admin_cnpj);

CREATE INDEX IF NOT EXISTS view_fiis_info_sector_unaccent_idx ON view_fiis_info (public.unaccent_ci(sector));
CREATE INDEX IF NOT EXISTS view_fiis_info_sub_sector_unaccent_idx ON view_fiis_info (public.unaccent_ci(sub_sector));
CREATE INDEX IF NOT EXISTS view_fiis_info_classification_unaccent_idx ON view_fiis_info (public.unaccent_ci(classification));
CREATE INDEX IF NOT EXISTS view_fiis_info_management_type_unaccent_idx ON view_fiis_info (public.unaccent_ci(management_type));
CREATE INDEX IF NOT EXISTS view_fiis_info_target_market_unaccent_idx ON view_fiis_info (public.unaccent_ci(target_market));

COMMENT ON MATERIALIZED VIEW view_fiis_info IS 'Informações sobre cada FII listado (1 linha por fundo).||ask:intents=cadastro,perfil,info;keywords=cadastro,dados,ficha,cnpj,site,administrador,custodiante';
COMMENT ON COLUMN view_fiis_info.fii_cnpj IS 'CNPJ do FII (identificador único).|CNPJ';
COMMENT ON COLUMN view_fiis_info.ticker IS 'Código do fundo na B3.|Código FII';
COMMENT ON COLUMN view_fiis_info.ticker_full_name IS 'Nome completo do ticker.|Nome completo';
COMMENT ON COLUMN view_fiis_info.b3_name IS 'Nome de pregão na B3.|Nome B3';
COMMENT ON COLUMN view_fiis_info.classification IS 'Classificação oficial do fundo.|Classificação';
COMMENT ON COLUMN view_fiis_info.sector IS 'Setor de atuação do fundo.|Setor';
COMMENT ON COLUMN view_fiis_info.sub_sector IS 'Tipo de indústria.|Tipo de indústria';
COMMENT ON COLUMN view_fiis_info.management_type IS 'Tipo de gestão (ativa/passiva).|Tipo de gestão';
COMMENT ON COLUMN view_fiis_info.target_market IS 'Público alvo.|Público alvo';
COMMENT ON COLUMN view_fiis_info.is_exclusive IS 'Indica se o fundo é exclusivo (boolean).|Fundo exclusivo';
COMMENT ON COLUMN view_fiis_info.isin IS 'Código ISIN do fundo.|Código ISIN"';
COMMENT ON COLUMN view_fiis_info.ipo_date IS 'Data do IPO do fundo.|Data IPO';
COMMENT ON COLUMN view_fiis_info.website_url IS 'URL oficial do fundo.|Site oficial';
COMMENT ON COLUMN view_fiis_info.admin_name IS 'Nome do administrador do fundo.|Administrador';
COMMENT ON COLUMN view_fiis_info.admin_cnpj IS 'CNPJ do administrador.|CNPJ administrador';
COMMENT ON COLUMN view_fiis_info.custodian_name IS 'Nome do custodiante do fundo.|Custodiante';
COMMENT ON COLUMN view_fiis_info.ifil_weight_pct IS 'Participação percentual no IFIL.|Participação IFIL';
COMMENT ON COLUMN view_fiis_info.ifix_weight_pct IS 'Participação percentual no IFIX.|Participação IFIX';
COMMENT ON COLUMN view_fiis_info.dividend_yield_monthly IS 'Dividend yield mensal.|DY mensal';
COMMENT ON COLUMN view_fiis_info.dividend_yield IS 'Dividend yield.|DY';
COMMENT ON COLUMN view_fiis_info.sum_dividend_yearly IS 'Soma dos dividendos pago por cota anual.|Dividendos pagos no ano';
COMMENT ON COLUMN view_fiis_info.last_dividend_amount IS 'Último dividendo pago por cota.|Último dividendo';
COMMENT ON COLUMN view_fiis_info.last_dividends_payment_date IS 'Data do último pagamento de dividendo.|Data pagamento';
COMMENT ON COLUMN view_fiis_info.market_cap_value IS 'Valor de mercado do fundo.|Valor de mercado';
COMMENT ON COLUMN view_fiis_info.enterprise_value IS 'Enterprise value (valor da firma).|Enterprise value';
COMMENT ON COLUMN view_fiis_info.price_book_ratio IS 'Índice Preço/Patrimônio.|P/VP';
COMMENT ON COLUMN view_fiis_info.equity_per_share IS 'Patrimônio líquido por cota.|VPA';
COMMENT ON COLUMN view_fiis_info.revenue_per_share IS 'Receita por cota.|Receita por cota';
COMMENT ON COLUMN view_fiis_info.payout_ratio_pct IS 'Payout ratio em percentual.|Dividend Payout Ratio';
COMMENT ON COLUMN view_fiis_info.growth_rate_pct IS 'Taxa de crescimento percentual.|Crescimento do patrimônio';
COMMENT ON COLUMN view_fiis_info.cap_rate_pct IS 'Cap rate percentual.|Taxa de capitalização';
COMMENT ON COLUMN view_fiis_info.volatility_pct IS 'Volatilidade percentual.|Volatilidade';
COMMENT ON COLUMN view_fiis_info.sharpe_ratio IS 'Índice de Sharpe.|Sharpe';
COMMENT ON COLUMN view_fiis_info.treynor_ratio IS 'Índice de Treynor.|Treynor';
COMMENT ON COLUMN view_fiis_info.jensen_alpha IS 'Alfa de Jensen.|Jensen';
COMMENT ON COLUMN view_fiis_info.beta_index IS 'Índice beta.|Beta';
COMMENT ON COLUMN view_fiis_info.leverage_ratio IS 'Índice de alavancagem.|Alavancagem';
COMMENT ON COLUMN view_fiis_info.equity_value IS 'Patrimônio líquido.|PL Total';
COMMENT ON COLUMN view_fiis_info.shares_count IS 'Quantidade de cotas emitidas.|Cotas emitidas';
COMMENT ON COLUMN view_fiis_info.variation_year_pct IS 'Variação efetiva no ano (%).|YTD';
COMMENT ON COLUMN view_fiis_info.variation_month_pct IS 'Variação efetiva no mês (%).|MTD';
COMMENT ON COLUMN view_fiis_info.equity_month_pct IS 'Variação patrimonial mensal (%).|PL mês';
COMMENT ON COLUMN view_fiis_info.shareholders_count IS 'Número de cotistas.|Cotistas';
COMMENT ON COLUMN view_fiis_info.dividend_reserve IS 'Dividendos a distribuir.|Reserva de dividendos';
COMMENT ON COLUMN view_fiis_info.admin_fee_due IS 'Taxa de administração a pagar.|Administração devida';
COMMENT ON COLUMN view_fiis_info.perf_fee_due IS 'Taxa de performance a pagar.|Performance devida';
COMMENT ON COLUMN view_fiis_info.total_cash_value IS 'Valor total em caixa.|Disponibilidades';
COMMENT ON COLUMN view_fiis_info.expected_revenue IS 'Receita esperada.|Projeção receita';
COMMENT ON COLUMN view_fiis_info.liabilities_total IS 'Total de passivos.|Passivos';
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
COMMENT ON COLUMN view_fiis_info.revenue_due_over_36m_pct IS 'Receita a vencer acima de 36 meses (%).|Receita Longo prazo';
COMMENT ON COLUMN view_fiis_info.revenue_due_undetermined_pct IS 'Receita a vencer sem prazo definido (%).|Receita sem prazo';
COMMENT ON COLUMN view_fiis_info.revenue_igpm_pct IS 'Receita indexada ao IGP-M (%).|Receita Indexada IGPM';
COMMENT ON COLUMN view_fiis_info.revenue_inpc_pct IS 'Receita indexada ao INPC (%).|Receita Indexada INPC';
COMMENT ON COLUMN view_fiis_info.revenue_ipca_pct IS 'Receita indexada ao IPCA (%).|Receita Indexada IPCA';
COMMENT ON COLUMN view_fiis_info.revenue_incc_pct IS 'Receita indexada ao INCC (%).|Receita Indexada INCC';
COMMENT ON COLUMN view_fiis_info.users_ranking IS 'Ranking atribuído por usuários.|Ranking usuários';
COMMENT ON COLUMN view_fiis_info.users_rank_movement IS 'Movimento do ranking de usuários.|Movimento usuários';
COMMENT ON COLUMN view_fiis_info.sirios_ranking IS 'Ranking atribuído pelo sistema Sirios.|Ranking Sirios';
COMMENT ON COLUMN view_fiis_info.sirios_rank_movement IS 'Movimento do ranking Sirios.|Movimento Sirios';
COMMENT ON COLUMN view_fiis_info.ifix_ranking IS 'Ranking relativo ao índice IFIX.|Ranking IFIX';
COMMENT ON COLUMN view_fiis_info.ifix_rank_movement IS 'Movimento de posição no IFIX.|Movimento IFIX';
COMMENT ON COLUMN view_fiis_info.ifil_ranking IS 'Ranking relativo ao índice IFIL.|Ranking IFIL';
COMMENT ON COLUMN view_fiis_info.ifil_rank_movement IS 'Movimento de posição no IFIL.|Movimento IFIL';
COMMENT ON COLUMN view_fiis_info.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_info.updated_at IS 'Data da última atualização do registro.|Atualizado em';

ALTER MATERIALIZED VIEW public.view_fiis_info OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_info;

-- =====================================================================
-- VIEW: view_fiis_history_dividends
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_dividends CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_dividends AS
SELECT
    bt.ticker              AS ticker,
    hd.traded_until        AS traded_until_date,
    hd.payment_date        AS payment_date,
    hd.amount              AS dividend_amount
FROM basics_tickers bt
JOIN hist_dividends hd ON bt.ticker = hd.ticker
ORDER BY bt.ticker ASC, hd.traded_until DESC, hd.payment_date DESC;

CREATE UNIQUE INDEX idx_fiis_hist_dividends 
    ON view_fiis_history_dividends(ticker, traded_until_date, payment_date);

COMMENT ON MATERIALIZED VIEW view_fiis_history_dividends IS 'Histórico de dividendos por FII.||ask:intents=dividends,historico;keywords=dividendo,provento,histórico,historico,último,mais recente;latest_words=último,mais recente';
COMMENT ON COLUMN view_fiis_history_dividends.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_dividends.traded_until_date IS 'Data limite de negociação com direito ao dividendo.|Data limite de negociação';
COMMENT ON COLUMN view_fiis_history_dividends.payment_date IS 'Data de pagamento do dividendo.|Data de pagamento';
COMMENT ON COLUMN view_fiis_history_dividends.dividend_amount IS 'Valor do dividendo pago.|Valor do dividendo';

ALTER MATERIALIZED VIEW public.view_fiis_history_dividends OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_dividends;

-- =====================================================================
-- VIEW: view_fiis_history_assets
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_assets CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_assets AS
SELECT
    bt.ticker        AS ticker,
    at.asset         AS asset_name,
	at.asset_class   AS asset_class,
    at.address       AS asset_address,
    at.total_area    AS total_area,
    at.number_units  AS units_count,
    at.space_vacancy AS vacancy_pct,
    at.non_compliance AS non_compliant_pct,
	at.asset_status	 AS assets_status,
    at.created_at    AS created_at,
    at.updated_at    AS updated_at
FROM basics_tickers bt
JOIN assets_tickers at ON bt.ticker = at.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_assets 
    ON view_fiis_history_assets(ticker, asset_class, asset_name, asset_address, assets_status);

COMMENT ON MATERIALIZED VIEW view_fiis_history_assets IS 'Ativos (imóveis) pertencentes a cada FII.||ask:intents=ativos,imoveis;keywords=imóvel,imoveis,ativo,ativos,asset,endereço';
COMMENT ON COLUMN view_fiis_history_assets.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_assets.asset_name IS 'Nome do ativo (imóvel).|Nome do ativo';
COMMENT ON COLUMN view_fiis_history_assets.asset_class IS 'Classe de ativo.|Classe';
COMMENT ON COLUMN view_fiis_history_assets.asset_address IS 'Endereço do ativo.|Endereço';
COMMENT ON COLUMN view_fiis_history_assets.total_area IS 'Área total do ativo em m².|Área total';
COMMENT ON COLUMN view_fiis_history_assets.units_count IS 'Número de unidades do ativo.|Unidades';
COMMENT ON COLUMN view_fiis_history_assets.vacancy_pct IS 'Taxa de vacância do ativo (%).|Vacância';
COMMENT ON COLUMN view_fiis_history_assets.non_compliant_pct IS 'Taxa de inadimplência do ativo (%).|Inadimplência';
COMMENT ON COLUMN view_fiis_history_assets.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_assets.updated_at IS 'Data da última atualização do registro.|Atualizado em';

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
    pt.initiation_date AS initiation_date,
    pt.value_of_cause  AS cause_value,
    pt.process_parts   AS process_parts,
    pt.chance_of_loss  AS loss_risk_pct,
    pt.main_facts      AS main_facts,
    pt.analysis_impact_loss AS loss_impact_analysis,
	pt.created_at    AS created_at,
    pt.updated_at    AS updated_at
FROM basics_tickers bt
JOIN process_tickers pt ON bt.ticker = pt.ticker
ORDER BY bt.ticker ASC;

CREATE UNIQUE INDEX idx_fiis_judicial 
    ON view_fiis_history_judicial(ticker, process_number);

COMMENT ON MATERIALIZED VIEW view_fiis_history_judicial IS 'Processos judiciais relacionados a cada FII.||ask:intents=judicial,processos;keywords=judicial,processo,ação,instância,valor da causa,riscos';
COMMENT ON COLUMN view_fiis_history_judicial.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_judicial.process_number IS 'Número do processo judicial.|Identificador do processo';
COMMENT ON COLUMN view_fiis_history_judicial.judgment IS 'Local ou instância do julgamento.|Órgão julgador';
COMMENT ON COLUMN view_fiis_history_judicial.instance IS 'Instância judicial (ex.: 1ª, 2ª).|Instância';
COMMENT ON COLUMN view_fiis_history_judicial.initiation_date IS 'Data de abertura do processo.|Abertura';
COMMENT ON COLUMN view_fiis_history_judicial.cause_value IS 'Valor da causa.|Montante em disputa';
COMMENT ON COLUMN view_fiis_history_judicial.process_parts IS 'Partes envolvidas no processo.|Partes';
COMMENT ON COLUMN view_fiis_history_judicial.loss_risk_pct IS 'Probabilidade de perda (%).|Risco de perda';
COMMENT ON COLUMN view_fiis_history_judicial.main_facts IS 'Fatos principais do processo.|Fatos principais';
COMMENT ON COLUMN view_fiis_history_judicial.loss_impact_analysis IS 'Análise do impacto em caso de perda.|Análise de impacto';
COMMENT ON COLUMN view_fiis_history_judicial.created_at IS 'Data de criação do registro.|Criado em';
COMMENT ON COLUMN view_fiis_history_judicial.updated_at IS 'Data da última atualização do registro.|Atualizado em';

ALTER MATERIALIZED VIEW public.view_fiis_history_judicial OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_judicial;

-- =====================================================================
-- VIEW: view_fiis_history_prices
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_prices CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_prices AS
SELECT
    bt.ticker          AS ticker,
    p.price_ref_date   AS price_date,
    p.close_price      AS close_price,
    p.adj_close_price  AS adj_close_price,
    p.open_price       AS open_price,
    p.daily_range      AS daily_range,
    p.max_price        AS max_price,
    p.min_price        AS min_price
FROM basics_tickers bt
JOIN price_tickers p ON bt.ticker = p.ticker
ORDER BY bt.ticker ASC, p.price_ref_date DESC;

CREATE UNIQUE INDEX idx_fiis_history_prices 
    ON view_fiis_history_prices(ticker, price_date);

COMMENT ON MATERIALIZED VIEW view_fiis_history_prices IS 'Histórico de preços dos FIIs.||ask:intents=precos,historico;keywords=preço,precos,fechamento,abertura,alta,baixa,histórico,serie temporal,gráfico;latest_words=último,mais recente';
COMMENT ON COLUMN view_fiis_history_prices.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_prices.price_date IS 'Data de referência do preço.|Data de referência';
COMMENT ON COLUMN view_fiis_history_prices.close_price IS 'Preço de fechamento.|Fechamento';
COMMENT ON COLUMN view_fiis_history_prices.adj_close_price IS 'Preço de fechamento ajustado.|Preço ajustado';
COMMENT ON COLUMN view_fiis_history_prices.open_price IS 'Preço de abertura.|Abertura';
COMMENT ON COLUMN view_fiis_history_prices.daily_range IS 'Variação diária de preço.|Variação do dia';
COMMENT ON COLUMN view_fiis_history_prices.max_price IS 'Preço máximo no dia.|Máxima';
COMMENT ON COLUMN view_fiis_history_prices.min_price IS 'Preço mínimo no dia.|Mínima';

ALTER MATERIALIZED VIEW public.view_fiis_history_prices OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_prices;


-- =====================================================================
-- VIEW: view_fiis_history_news
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_fiis_history_news CASCADE;

CREATE MATERIALIZED VIEW view_fiis_history_news AS
SELECT
    bt.ticker           AS ticker,
    mn.news_url         AS news_url,
    mn.news_topic       AS news_source,
    mn.news_title       AS news_title,
    mn.news_date        AS news_date,
    mn.news_tags        AS news_tags,
    mn.news_description AS news_description
FROM basics_tickers bt
JOIN market_news mn 
  ON (mn.news_title ILIKE '%' || bt.ticker || '%' OR 
      mn.news_description ILIKE '%' || bt.ticker || '%')
ORDER BY bt.ticker;

CREATE UNIQUE INDEX idx_fiis_history_news 
    ON view_fiis_history_news(ticker, news_url);
CREATE INDEX IF NOT EXISTS idx_news_ticker_date
ON view_fiis_history_news (ticker, news_date DESC);

COMMENT ON MATERIALIZED VIEW view_fiis_history_news IS 'Notícias relacionadas aos FIIs.||ask:intents=noticias,news;keywords=notícia,noticias,news,título,fonte,matéria,histórico,divulgação;latest_words=último,mais recente';
COMMENT ON COLUMN view_fiis_history_news.ticker IS 'Ticker do FII.|Código FII';
COMMENT ON COLUMN view_fiis_history_news.news_url IS 'URL da notícia.|Link da notícia';
COMMENT ON COLUMN view_fiis_history_news.news_source IS 'Fonte do conteúdo da notícia.|Origem';
COMMENT ON COLUMN view_fiis_history_news.news_title IS 'Título da notícia.|Título';
COMMENT ON COLUMN view_fiis_history_news.news_date IS 'Data da notícia.|Data';
COMMENT ON COLUMN view_fiis_history_news.news_tags IS 'Tags relacionadas à notícia.|Tags';
COMMENT ON COLUMN view_fiis_history_news.news_description IS 'Resumo ou descrição da notícia.|Resumo';

ALTER MATERIALIZED VIEW public.view_fiis_history_news OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_fiis_history_news;


-- =====================================================================
-- VIEW: view_market_indicators
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_market_indicators CASCADE;

CREATE MATERIALIZED VIEW view_market_indicators AS
SELECT 
    hi.date_indicators   AS indicator_date,
    hi.slug_indicators   AS indicator_name,
    hi.value_indicators  AS indicator_value
FROM public.hist_indicators hi
ORDER BY hi.date_indicators DESC, hi.slug_indicators ASC;

CREATE UNIQUE INDEX idx_market_indicators 
    ON view_market_indicators(indicator_date, indicator_name);

COMMENT ON MATERIALIZED VIEW view_market_indicators IS 'Indicadores de mercado históricos.||ask:intents=indicadores,mercado;keywords=ifix,ifil,ibov,cdi,selic,dólar,euro,indicadores';
COMMENT ON COLUMN view_market_indicators.indicator_date IS 'Data de referência do indicador.|Data';
COMMENT ON COLUMN view_market_indicators.indicator_name IS 'Nome ou identificador do indicador.|Indicador';
COMMENT ON COLUMN view_market_indicators.indicator_value IS 'Valor registrado do indicador.|Valor';

ALTER MATERIALIZED VIEW public.view_market_indicators OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_market_indicators;


-- =====================================================================
-- VIEW: view_history_taxes
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS view_history_taxes CASCADE;

CREATE MATERIALIZED VIEW view_history_taxes AS
SELECT 
    ht.date_taxes        AS tax_date,
    ht.cdi_taxes         AS cdi_rate_pct,
    ht.selic_taxes       AS selic_rate_pct,
    ht.ibovespa_taxes    AS ibov_points,
    ht.ibovespa_variation AS ibov_var_pct,
    ht.ifix_taxes        AS ifix_points,
    ht.ifix_variation    AS ifix_var_pct,
    ht.ifil_taxes        AS ifil_points,
    ht.ifil_variation    AS ifil_var_pct,
    ht.usd_buy           AS usd_buy_value,
    ht.usd_sell          AS usd_sell_value,
    ht.usd_variation     AS usd_var_pct,
    ht.eur_buy           AS eur_buy_value,
    ht.eur_sell          AS eur_sell_value,
    ht.eur_variation     AS eur_var_pct
FROM public.hist_taxes ht
ORDER BY ht.date_taxes DESC;

CREATE UNIQUE INDEX idx_history_taxes 
    ON view_history_taxes(tax_date);

COMMENT ON MATERIALIZED VIEW view_history_taxes IS 'Histórico diário de taxas e índices.||ask:intents=taxas,diario;keywords=ifix,ifil,ibov,cdi,selic,dólar,euro,diário';
COMMENT ON COLUMN view_history_taxes.tax_date IS 'Data de referência.|Data';
COMMENT ON COLUMN view_history_taxes.cdi_rate_pct IS 'Taxa CDI (%).|CDI';
COMMENT ON COLUMN view_history_taxes.selic_rate_pct IS 'Taxa SELIC (%).|SELIC';
COMMENT ON COLUMN view_history_taxes.ibov_points IS 'Pontuação do índice IBOVESPA.|Pontuação IBOVESPA';
COMMENT ON COLUMN view_history_taxes.ibov_var_pct IS 'Variação percentual do IBOVESPA.|Variação IBOVESPA';
COMMENT ON COLUMN view_history_taxes.ifix_points IS 'Pontuação do índice IFIX.|Pontuação IFIX';
COMMENT ON COLUMN view_history_taxes.ifix_var_pct IS 'Variação percentual do IFIX.|Variação IFIX';
COMMENT ON COLUMN view_history_taxes.ifil_points IS 'Pontuação do índice IFIL.|Pontuação IFIL';
COMMENT ON COLUMN view_history_taxes.ifil_var_pct IS 'Variação percentual do IFIL.|Variação IFIL';
COMMENT ON COLUMN view_history_taxes.usd_buy_value IS 'Cotação de compra do dólar.|USD compra';
COMMENT ON COLUMN view_history_taxes.usd_sell_value IS 'Cotação de venda do dólar.|USD venda';
COMMENT ON COLUMN view_history_taxes.usd_var_pct IS 'Variação percentual do dólar.|USD variação';
COMMENT ON COLUMN view_history_taxes.eur_buy_value IS 'Cotação de compra do euro.|EURO compra';
COMMENT ON COLUMN view_history_taxes.eur_sell_value IS 'Cotação de venda do euro.|EURO venda';
COMMENT ON COLUMN view_history_taxes.eur_var_pct IS 'Variação percentual do euro.|EURO variação';

ALTER MATERIALIZED VIEW public.view_history_taxes OWNER TO edge_user;
REFRESH MATERIALIZED VIEW view_history_taxes;

