# AWS Cost Allocation Tagging Strategy

**ACE Report Hub - Cost Management**

---

## Overview

This document outlines the AWS cost allocation tagging strategy for the ACE Report Hub project. All AWS resources used by this project are tagged consistently to enable cost tracking, budget management, and resource lifecycle management.

---

## Tagging Strategy

### Standard Tags (2 Required Tags)

All AWS resources in this project use the following tags:

```
Project: ace-report-hub
Purpose: production
```

### Tag Definitions

| Tag Key | Tag Value | Description |
|---------|-----------|-------------|
| `Project` | `ace-report-hub` | Identifies which project owns this resource. Used for cost allocation across multiple projects. |
| `Purpose` | `production` | Indicates the resource's lifecycle stage. Options: `production`, `experiment`, `temporary`, `archive` |

---

## AWS Resources Used

### 1. AWS Bedrock (Primary Service)

**Service**: Amazon Bedrock Runtime
**Region**: us-east-1
**Model**: Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
**Usage**: AI-generated executive summaries for weekly ACE reports
**Cost Driver**: Pay-per-API-call (tokens processed)

**Implementation**: Tags are applied via boto3 session configuration in `bedrock_client.py`

---

## How to Enable Cost Allocation Tags in AWS

### Step 1: Activate Cost Allocation Tags

1. **Navigate to AWS Billing Console**:
   ```
   https://console.aws.amazon.com/billing/home#/tags
   ```

2. **Activate Tags**:
   - Find "Project" in the list → Click "Activate"
   - Find "Purpose" in the list → Click "Activate"

3. **Wait for Data**:
   - Cost allocation data typically appears within 24 hours after activation
   - Historical data before activation is NOT retroactively tagged

### Step 2: View Cost Reports by Tag

1. **Go to Cost Explorer**:
   ```
   https://console.aws.amazon.com/cost-management/home#/cost-explorer
   ```

2. **Group by Tag**:
   - Click "Group by" → Select "Tag" → Choose "Project"
   - Filter by `Project = ace-report-hub` to see costs for this project only

3. **Create Budget Alerts**:
   ```
   https://console.aws.amazon.com/billing/home#/budgets
   ```
   - Create budget based on `Project:ace-report-hub` tag
   - Set monthly budget threshold and email alerts

---

## Cost Tracking Use Cases

### 1. "Which project is costing me money?"
- Group Cost Explorer by `Project` tag
- Compare costs across: `ace-report-hub`, `context-engine`, `billing-manager`, etc.

### 2. "Can I delete this resource to save money?"
- Filter resources by `Purpose` tag:
  - `production`: Keep running, actively used
  - `experiment`: Review monthly, delete if testing complete
  - `temporary`: Delete after testing (safe to remove)
  - `archive`: Not actively used, consider deletion

### 3. "How much does ACE Report Hub cost per month?"
- Cost Explorer → Filter by `Project:ace-report-hub`
- View breakdown by service (Bedrock costs)

---

## Tagging Implementation

### For Python/boto3 (Current Project)

Default tags are configured in the boto3 session initialization:

```python
import boto3

# Create session with default tags
session = boto3.Session()
session.set_default_tags({
    'Project': 'ace-report-hub',
    'Purpose': 'production'
})

# All clients created from this session inherit tags
bedrock_runtime = session.client('bedrock-runtime', region_name='us-east-1')
```

**Note**: Bedrock Runtime API calls are pay-per-use and don't support resource-level tagging. However, setting default session tags ensures any other AWS services (S3, Lambda, etc.) added in the future will be automatically tagged.

### For AWS CLI

```bash
# Example: Creating an S3 bucket with tags
aws s3api create-bucket \
  --bucket ace-report-hub-data \
  --region us-east-1 \
  --tags Key=Project,Value=ace-report-hub Key=Purpose,Value=production
```

### For AWS CloudFormation

```yaml
Resources:
  MyResource:
    Type: AWS::S3::Bucket
    Properties:
      Tags:
        - Key: Project
          Value: ace-report-hub
        - Key: Purpose
          Value: production
```

### For Terraform

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "ace-report-hub-data"

  tags = {
    Project = "ace-report-hub"
    Purpose = "production"
  }
}
```

---

## Cost Optimization Recommendations

### Current Costs (Bedrock)

- **Model**: Claude Sonnet 4.5
- **Usage Pattern**: 1x weekly report generation
- **Token Usage**: ~300 tokens per summary (configured in `bedrock_client.py:128`)
- **Estimated Monthly Cost**: Low (< $1/month for typical usage)

### Optimization Strategies

1. **Monitor Token Usage**:
   - Current max_tokens setting: 300
   - Review actual token consumption in AWS CloudWatch
   - Adjust max_tokens if summaries consistently use less

2. **Batch Processing**:
   - Current: 1 API call per weekly report
   - Consider: Generate multiple reports in single call if processing increases

3. **Model Selection**:
   - Current: Claude Sonnet 4.5 (high quality, moderate cost)
   - Alternative: Claude Haiku (faster, lower cost) if summary quality acceptable

4. **Cache Optimization**:
   - Enable Bedrock prompt caching if using repeated context
   - Current implementation: No caching (each call is independent)

---

## Resource Lifecycle Management

### Production Resources (`Purpose: production`)

- **Review Frequency**: Quarterly
- **Action**: Monitor costs, optimize usage
- **Delete**: Only if project is fully decommissioned

### Experimental Resources (`Purpose: experiment`)

- **Review Frequency**: Monthly
- **Action**: Evaluate if experiment is complete
- **Delete**: After testing concludes, data is backed up

### Temporary Resources (`Purpose: temporary`)

- **Review Frequency**: Weekly
- **Action**: Delete immediately after testing
- **Delete**: Safe to remove anytime, no data retention needed

### Archived Resources (`Purpose: archive`)

- **Review Frequency**: Quarterly
- **Action**: Assess if still needed for reference
- **Delete**: If data is no longer needed or can be stored cheaper (e.g., Glacier)

---

## Troubleshooting

### Tags Not Showing in Cost Explorer

- **Issue**: Tags activated but no cost data visible
- **Solution**: Wait 24 hours after activation
- **Verify**: Check that resources were created AFTER tag activation

### Bedrock Costs Not Tagged

- **Issue**: Bedrock API call costs don't appear with Project tag
- **Explanation**: Bedrock Runtime is pay-per-API-call, not a persistent resource
- **Solution**: View Bedrock costs under "Service" dimension in Cost Explorer
- **Workaround**: Use AWS Cost Categories to group Bedrock costs by account/project

### Historical Costs Not Tagged

- **Issue**: Costs before tag activation don't show tags
- **Explanation**: AWS doesn't retroactively apply tags to historical costs
- **Solution**: Tags only apply to costs incurred AFTER activation date

---

## Compliance and Governance

### Required Tags (Enforced)

- `Project`: REQUIRED - Must be set on all resources
- `Purpose`: REQUIRED - Must be one of: production, experiment, temporary, archive

### Tag Naming Conventions

- Tag Keys: PascalCase (e.g., `Project`, `Purpose`)
- Tag Values: lowercase-with-hyphens (e.g., `ace-report-hub`, `production`)

### Automated Enforcement

Consider implementing AWS Config rules to enforce tagging:

```yaml
# Example AWS Config Rule (not currently implemented)
RequiredTags:
  - Project
  - Purpose
```

---

## Additional Resources

- [AWS Cost Allocation Tags Documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [AWS Cost Explorer User Guide](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)
- [AWS Budgets](https://aws.amazon.com/aws-cost-management/aws-budgets/)

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-11-05 | Initial cost allocation tagging strategy created | Claude Code |

---

## Support

For questions about AWS cost allocation tags or this project's tagging strategy:
- Review this documentation first
- Check AWS Billing Console for cost reports
- Create a GitHub issue for project-specific questions
