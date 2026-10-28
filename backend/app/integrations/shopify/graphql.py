"""GraphQL query templates for the Shopify Admin API (2026-07 baseline).

Field names follow the Admin GraphQL schema; verify against the current
schema reference before any live run (see Part 02 spec section 96).
"""

SHOP_QUERY = """
query Shop {
  shop { name currencyCode timezoneAbbreviation }
}
"""

PRODUCTS_QUERY = """
query Products($after: String, $updatedAfter: DateTime!) {
  products(first: 50, after: $after, query: "updated_at:>='$updatedAfter'") {
    edges {
      node {
        id title handle vendor productType status createdAt updatedAt
        variants(first: 50) {
          edges {
            node {
              id sku title price compareAtPrice
              inventoryItem { id }
            }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

ORDERS_QUERY = """
query Orders($after: String, $updatedAfter: DateTime!, $updatedBefore: DateTime!) {
  orders(first: 50, after: $after,
         query: "updated_at:>='$updatedAfter' AND updated_at:<='$updatedBefore'") {
    edges {
      node {
        id name createdAt updatedAt
        displayFinancialStatus displayFulfillmentStatus
        currencyCode subtotalPriceSet { shopMoney { amount } }
        totalShippingPriceSet { shopMoney { amount } }
        totalTaxSet { shopMoney { amount } }
        totalDiscountsSet { shopMoney { amount } }
        currentTotalPriceSet { shopMoney { amount } }
        cancelledAt sourceName
        customer { id }
        lineItems(first: 50) {
          edges {
            node {
              id title quantity sku
              variant { id product { id } }
              unitPriceSet { shopMoney { amount } }
            }
          }
        }
        refunds(first: 20) {
          edges {
            node { id createdAt totalRefundedSet { shopMoney { amount } } }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

JOURNEY_QUERY = """
query Journey($orderId: ID!) {
  order(id: $orderId) {
    id
    customerJourneySummary {
      ready
      daysToConversion
      momentsCount
      firstVisit { landingPage source referrerUrl utmParameters { source medium campaign content term } }
      lastVisit { landingPage source referrerUrl utmParameters { source medium campaign content term } }
    }
  }
}
"""

BULK_PRODUCTS_QUERY = '''
mutation BulkProducts {
  bulkOperationRunQuery(
    query: """
      {
        products {
          edges { node { id title handle vendor productType status createdAt updatedAt } }
        }
      }
    """
  ) { bulkOperation { id status } userErrors { field message } }
}
'''

BULK_ORDERS_QUERY = '''
mutation BulkOrders {
  bulkOperationRunQuery(
    query: """
      {
        orders {
          edges { node { id name createdAt updatedAt
            displayFinancialStatus displayFulfillmentStatus currencyCode
            subtotalPriceSet { shopMoney { amount } }
            totalShippingPriceSet { shopMoney { amount } }
            totalTaxSet { shopMoney { amount } }
            totalDiscountsSet { shopMoney { amount } }
            currentTotalPriceSet { shopMoney { amount } }
            cancelledAt sourceName
            lineItems { edges { node { id title quantity sku variant { id product { id } }
              unitPriceSet { shopMoney { amount } } } } }
            refunds { edges { node { id createdAt totalRefundedSet { shopMoney { amount } } } } }
          } }
        }
      }
    """
  ) { bulkOperation { id status } userErrors { field message } }
}
'''

CURRENT_BULK_OPERATION_QUERY = """
query CurrentBulk {
  currentBulkOperation {
    id status errorCode url
    objectCount
  }
}
"""
