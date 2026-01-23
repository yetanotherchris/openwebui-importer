# Claude PR Review Bot Setup

This repository uses the official [Claude Code Action](https://github.com/anthropics/claude-code-action) to provide AI-powered code reviews.

## Quick Setup

### Option 1: Using Claude Code CLI (Easiest)

1. Install Claude Code CLI: https://code.claude.com/docs/en/install
2. Run the setup command:
   ```bash
   claude
   /install-github-app
   ```
3. Follow the prompts to:
   - Install the GitHub App on your repository
   - Configure the required secrets automatically

### Option 2: Manual Setup

#### Step 1: Get an Anthropic API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

#### Step 2: Install Claude GitHub App

1. Visit https://github.com/apps/claude
2. Click "Install"
3. Select this repository (`yetanotherchris/openwebui-importer`)
4. Complete the installation
5. Note down the **App ID** from the app settings

#### Step 3: Generate GitHub App Private Key

1. Go to your GitHub App settings
2. Scroll to "Private keys" section
3. Click "Generate a private key"
4. Download the `.pem` file
5. Copy the entire contents of the file

#### Step 4: Add Repository Secrets

Go to your repository: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Add these three secrets:

| Secret Name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (sk-ant-...) |
| `GITHUB_APP_ID` | Your GitHub App ID (numeric) |
| `GITHUB_APP_PRIVATE_KEY` | Contents of the .pem file (entire file including BEGIN/END lines) |

## How to Use

### Interactive Reviews (Comment-Triggered)

In any PR or issue, mention @claude with your request:

```
@claude review this pull request
```

```
@claude can you check the security of this authentication code?
```

```
@claude suggest improvements for performance
```

### Automatic Reviews (Optional)

To enable automatic reviews on every PR:

1. Edit `.github/workflows/claude-pr-review.yml`
2. Uncomment the `pull_request:` trigger section
3. Customize the review prompt as needed

## Workflow File

The workflow is located at: `.github/workflows/claude-pr-review.yml`

Current configuration:
- **Triggers**: @claude mentions in PR/issue comments
- **Permissions**: Can read code, write comments, make suggestions
- **Model**: Claude (latest version from Anthropic)

## Troubleshooting

### "Resource not accessible by integration" error
- Check that repository secrets are set correctly
- Verify the GitHub App has proper repository permissions
- Ensure workflow permissions include `pull-requests: write`

### Claude doesn't respond to @claude mentions
- Verify the workflow file exists in `.github/workflows/`
- Check that secrets are named exactly as specified (case-sensitive)
- Look at Actions tab to see if workflow runs are triggered

### API rate limits
- Anthropic API has usage limits based on your plan
- Monitor usage at https://console.anthropic.com/

## Cost Considerations

- Each PR review uses Claude API tokens
- Approximate cost: $0.10-$0.50 per detailed PR review (varies by PR size)
- Set up usage alerts in Anthropic Console to monitor spending

## Resources

- [Claude Code Action Documentation](https://github.com/anthropics/claude-code-action)
- [Claude API Documentation](https://docs.anthropic.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Support

For issues with:
- **The workflow**: Open an issue in this repository
- **Claude Code Action**: https://github.com/anthropics/claude-code-action/issues
- **Anthropic API**: support@anthropic.com
