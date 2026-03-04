OPENAPI=./openapi/openapi.yaml
OUT=./generated

.PHONY: gen
gen:
	rm -rf $(OUT)
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$(CURDIR):/local" openapitools/openapi-generator-cli:v7.6.0 \
	  generate -i /local/$(OPENAPI) -g python-fastapi \
	  -o /local/$(OUT) \
	  --additional-properties=packageName=generated,fastapiImplementationPackage=generated
	@sed -i 's/status:  = Query(/status: ProductStatus | None = Query(/g' $(OUT)/src/generated/apis/default_api.py
	@sed -i 's/status: ,/status: ProductStatus | None,/g' $(OUT)/src/generated/apis/default_api_base.py


run:
	docker compose -f docker-compose.yml up -d --remove-orphans --build