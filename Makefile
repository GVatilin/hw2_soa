OPENAPI=./openapi/openapi.yaml
OUT=./generated

.PHONY: gen
gen:
	rm -rf $(OUT)
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$(CURDIR):/local" openapitools/openapi-generator-cli \
	  generate -i /local/$(OPENAPI) -g python-fastapi \
	  -o /local/$(OUT) \
	  --additional-properties=packageName=generated,fastapiImplementationPackage=generated

run:
	docker compose -f docker-compose.yml up --remove-orphans --build