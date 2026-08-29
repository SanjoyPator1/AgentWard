# HAPI FHIR

Docker setup for the HAPI FHIR server that the agent and the fhir-mcp tool
layer both talk to. Needs to be resettable to a known state between eval runs,
that's the whole reason it's a container and not a shared long-lived instance.
