# Payment Failures

## Overview

This runbook covers common payment processing failures and their resolution steps.

## Common Error Types

### PaymentError: Gateway timeout

**Symptoms:**
- Payment processing fails with gateway timeout
- Error rate spikes during payment processing
- Database connection pool exhaustion may follow

**Root Causes:**
- Payment gateway (Stripe, Square) experiencing issues
- Network connectivity problems
- Gateway configuration changed

**Resolution Steps:**
1. Check payment gateway status page
2. Verify API keys are correct
3. Check network connectivity to gateway
4. Review recent deployments for configuration changes
5. Consider failover to backup gateway

### ConnectionError: Database pool exhausted

**Symptoms:**
- Database connection errors
- Application unable to process requests
- Connection pool size exceeded

**Root Causes:**
- Long-running queries blocking connections
- Connection leak in application code
- Sudden traffic spike

**Resolution Steps:**
1. Check for long-running queries
2. Restart application to reset connection pool
3. Increase pool size if needed
4. Review query performance

## Deployment Checklist

Before deploying payment-related changes:
- [ ] Run integration tests against staging gateway
- [ ] Verify API keys in environment
- [ ] Check connection pool settings
- [ ] Monitor error rates post-deploy

## Escalation

If issues persist after following this runbook:
1. Page the payments team
2. Check gateway vendor status
3. Consider rolling back deployment
