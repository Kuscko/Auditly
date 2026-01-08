terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }
}

provider "azurerm" {
  features {}
}

# -----------------------------------------------------------------------------
# Base variables (override via tfvars)
# -----------------------------------------------------------------------------
variable "location" {
  type        = string
  description = "Azure region"
  default     = "eastus"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for resource names"
  default     = "rapidrmf"
}

variable "tags" {
  type        = map(string)
  description = "Common tags"
  default = {
    owner = "rapidrmf-test"
    env   = "azure-test"
  }
}

# -----------------------------------------------------------------------------
# Existing resource group (use existing RG: kuscko-rg)
# -----------------------------------------------------------------------------
data "azurerm_resource_group" "rg" {
  name = "kuscko-rg"
}

# -----------------------------------------------------------------------------
# Storage account (evidence vault alternative or logs)
# -----------------------------------------------------------------------------
resource "azurerm_storage_account" "evidence" {
  name                     = "${var.name_prefix}store"
  resource_group_name      = data.azurerm_resource_group.rg.name
  location                 = data.azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  allow_nested_items_to_be_public = false
  min_tls_version          = "TLS1_2"
  https_traffic_only_enabled = true
  tags                     = var.tags

  blob_properties {
    versioning_enabled = true
  }

  # Network rules: Allow for initial setup; lock down post-deployment if needed
  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }
}

resource "azurerm_storage_container" "artifacts" {
  name                  = "artifacts"
  storage_account_name  = azurerm_storage_account.evidence.name
  container_access_type = "private"
}

# -----------------------------------------------------------------------------
# Key Vault (secrets + soft-delete/purge-protection on)
# -----------------------------------------------------------------------------
resource "azurerm_key_vault" "kv" {
  name                        = "${var.name_prefix}-kv"
  location                    = data.azurerm_resource_group.rg.location
  resource_group_name         = data.azurerm_resource_group.rg.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 90
  purge_protection_enabled    = true
  enable_rbac_authorization   = true
  public_network_access_enabled = false
  tags                        = var.tags
}

data "azurerm_client_config" "current" {}

# -----------------------------------------------------------------------------
# Log Analytics workspace (for diagnostics)
# -----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.name_prefix}-law"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# Note: Storage account diagnostic settings require targeting specific services
# (blob, table, queue, file) rather than the account itself.
# Uncomment and customize as needed:
# resource "azurerm_monitor_diagnostic_setting" "blob_diag" {
#   name                       = "${var.name_prefix}-blob-diag"
#   target_resource_id         = "${azurerm_storage_account.evidence.id}/blobServices/default"
#   log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
#   
#   enabled_log {
#     category = "StorageRead"
#   }
#   enabled_log {
#     category = "StorageWrite"
#   }
#   enabled_log {
#     category = "StorageDelete"
#   }
#   metric {
#     category = "Transaction"
#     enabled  = true
#   }
# }

# -----------------------------------------------------------------------------
# App Service plan + sample web app (HTTPS-only, TLS 1.2)
# Commented out due to subscription quota limits (0 Basic VMs available)
# -----------------------------------------------------------------------------
# resource "azurerm_service_plan" "app" {
#   name                = "${var.name_prefix}-plan"
#   resource_group_name = data.azurerm_resource_group.rg.name
#   location            = data.azurerm_resource_group.rg.location
#   os_type             = "Linux"
#   sku_name            = "B1"
#   tags                = var.tags
# }

# resource "azurerm_linux_web_app" "web" {
#   name                = "${var.name_prefix}-web"
#   resource_group_name = data.azurerm_resource_group.rg.name
#   location            = data.azurerm_resource_group.rg.location
#   service_plan_id     = azurerm_service_plan.app.id
#   https_only          = true
#
#   site_config {
#     minimum_tls_version = "1.2"
#     ftps_state          = "Disabled"
#   }
#
#   identity {
#     type = "SystemAssigned"
#   }
#
#   tags = var.tags
# }

# -----------------------------------------------------------------------------
# Outputs useful for RapidRMF evidence/system state
# -----------------------------------------------------------------------------
output "resource_group" {
  value = data.azurerm_resource_group.rg.name
}

output "storage_account" {
  value = azurerm_storage_account.evidence.name
}

output "storage_blob_endpoint" {
  value       = azurerm_storage_account.evidence.primary_blob_endpoint
  description = "Blob endpoint for evidence uploads (use with private networking rules)."
}

output "storage_account_id" {
  value       = azurerm_storage_account.evidence.id
  description = "Storage account resource ID"
}

output "key_vault" {
  value = azurerm_key_vault.kv.name
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.law.id
}

# output "web_app" {
#   value = azurerm_linux_web_app.web.name
# }
