# Database Errors

## Overview

Common database errors and their resolution.

## Connection Errors

### Connection refused
- Check database server is running
- Verify host/port configuration
- Check firewall rules

### Too many connections
- Check connection pool settings
- Look for connection leaks
- Increase max_connections if needed

## Query Errors

### Deadlock detected
- Review transaction isolation levels
- Ensure consistent lock ordering
- Reduce transaction scope

### Timeout
- Optimize slow queries
- Add appropriate indexes
- Check for table locks

## Data Errors

### Duplicate key violation
- Check application logic for race conditions
- Use UPSERT if appropriate
- Review unique constraints

### Foreign key violation
- Ensure referenced records exist
- Check deletion order
- Review cascade settings
