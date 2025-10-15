
## 🚀 Ordem recomendada de envio dos arquivos

1. `app/extractors/normalizers.py`
2. `app/executor/service.py`
3. `app/gateway/router.py`
4. `app/formatter/serializer.py`
5. `app/registry/{loader.py,service.py}`
6. 1 YAML (ex.: `view_fiis_info.yaml`)
7. `app/main.py`
8. `docker-compose.yml`
9. `tests/test_end_to_end.py`

---

Se concordar, **começamos pela Etapa 1 (Extractor Seguro)**.
👉 Me envie o conteúdo atual de `app/extractors/normalizers.py` para eu gerar o patch limpo (refactor com `default_factory` e cópia defensiva).

Posso também já criar o *commit message* padrão (`fix(extractors): safer defaults and copy isolation`) se quiser deixar padronizado.
Confirmo e seguimos?
