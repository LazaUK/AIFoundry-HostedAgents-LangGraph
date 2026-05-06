# Microsoft Foundry: LangGraph Workflow as a Hosted Agent (Agents v2)

This repo demonstrates how to build and deploy a **LangGraph-based Workflow** to **Microsoft Foundry Agent Service** using the **Foundry Toolkit for VS Code**. The agent implements a **Marketing Ad Generator** solution: a Copywriter drafts a haiku advertisement for a given product, and a Brand Guardian reviews it against pre-defined rules.

> [!TIP]
> Learn more about Foundry Hosted Agents on the [Microsoft Foundry documentation page](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents).

---

## 📑 Table of Contents
- [Part 1: Prerequisites](#part-1-prerequisites)
- [Part 2: Environment Setup](#part-2-environment-setup)
- [Part 5: Local Testing](#part-5-local-testing)
- [Part 6: Deploy to Foundry](#part-6-deploy-to-foundry)
- [Part 7: Testing the Deployed Agent](#part-7-testing-the-deployed-agent)

---

## Part 1: Prerequisites

Before getting started, ensure you have:

- **Azure Subscription** with access to provision **Microsoft Foundry**;
- **VS Code** with the **Microsoft Foundry Toolkit** extension installed.

> [!NOTE]
> You don't require Docker Desktop. The VS Code extension pushes Dockerfile to Azure Container Registry to bui;d required Docker image in the cloud.

---

## Part 2: Environment Setup

### 2.1 Microsoft Foundry Setup

Create a Microsoft Foundry **account** and **project**, then deploy a GPT model (e.g., `gpt-4.1-mini`).

### 2.2 RBAC Permissions

The VS Code extension handles most RBAC assignments automatically during deployment, including:

- `AcrPull` on Azure Container Registry for the Foundry managed identity;
- `Azure AI User` on the Foundry project for the agent identity.

### 2.3 Environment Variables

Updated the provided `.env` file in the names of our Foundry account and GPT model's deployment:

``` JSON
AZURE_OPENAI_ENDPOINT=https://<FOUNDRY_ACCOUNT>.openai.azure.com/
AZURE_AI_MODEL_DEPLOYMENT_NAME=<FOUNDRY_MODEL>
```

> [!NOTE]
> This solution uses an **Azure OpenAI endpoint**, not a Microsoft Foundry Project endpoint.

### 2.4 Configure `agent.yaml`

Update the provided `agent.yaml` with your agent name and resource allocation, if required:

``` YAML
kind: hosted
name: 'demo-langgraph-agent'
protocols:
  - protocol: responses
    version: 1.0.0
resources:
  cpu: '0.5'
  memory: '1.0Gi'
environment_variables:
  - name: AZURE_OPENAI_ENDPOINT
    value: ${AZURE_OPENAI_ENDPOINT}
  - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
    value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
```

### 2.5 Install Dependencies

Install required Python packages:

``` PowerShell
pip install -r requirements.txt
```

The `requirements.txt` includes:

``` JSON
azure-ai-agentserver-responses==1.0.0b5
azure-identity
openai
python-dotenv
debugpy
langgraph
langchain-openai
```
