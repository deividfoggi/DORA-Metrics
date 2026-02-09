"""
Azure Function App for DORA Deployment Frequency Collection
Collects deployment data from GitHub organization and stores in Azure SQL Database
"""

import azure.functions as func
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import pyodbc
from azure.identity import DefaultAzureCredential
import requests
import jwt
import time
import struct

app = func.FunctionApp()

# Configuration
GITHUB_ORG = os.environ.get("GITHUB_ORG_NAME")
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID")
GITHUB_APP_INSTALLATION_ID = os.environ.get("GITHUB_APP_INSTALLATION_ID")
GITHUB_APP_PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY")
GITHUB_DEPLOYMENT_ENVIRONMENTS = os.environ.get("GITHUB_DEPLOYMENT_ENVIRONMENTS", "")  # Comma-separated list, e.g., "production,staging"
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")  # Branch to track for PR merges
PR_LOOKBACK_HOURS = int(os.environ.get("PR_LOOKBACK_HOURS", "48"))  # Hours to look back for merged PRs
INCIDENT_LOOKBACK_HOURS = int(os.environ.get("INCIDENT_LOOKBACK_HOURS", "24"))  # Hours to look back for incidents
SQL_SERVER = os.environ.get("SQL_SERVER")
SQL_DATABASE = os.environ.get("SQL_DATABASE")


@app.schedule(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False,
              use_monitor=False) 
def deployment_frequency_collector(timer: func.TimerRequest) -> None:
    """
    Timer trigger function that runs every 5 minutes
    Collects deployment data from GitHub and stores in SQL Database
    """
    try:
        logging.info('Python timer trigger function started.')
        
        if timer.past_due:
            logging.info('The timer is past due!')
        
        try:
            # Get GitHub access token
            logging.info('[MAIN] Getting GitHub access token...')
            github_token = get_github_app_token()
            logging.info('[MAIN] GitHub token acquired')
            
            # Collect deployment data
            logging.info('[MAIN] Collecting deployment data from GitHub...')
            deployments = collect_github_deployments(github_token)
            logging.info(f"[MAIN] Collected {len(deployments)} deployments")
            
            # Store in SQL Database
            logging.info('[MAIN] Storing deployments in database...')
            store_deployments(deployments, github_token)
            logging.info("[MAIN] Deployments stored successfully")
            
            # Generate summary
            logging.info('[MAIN] Generating summary...')
            summary = generate_summary(deployments)
            logging.info(f"[MAIN] Summary: {summary}")
            logging.info('[MAIN] Function completed successfully')
            
        except Exception as e:
            logging.error(f"[MAIN] Error in deployment frequency collector: {type(e).__name__}: {str(e)}")
            import traceback
            logging.error(f"[MAIN] Full traceback: {traceback.format_exc()}")
            raise
    except:
        # Catch absolutely everything
        import sys
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"[CRITICAL] Unhandled exception: {error_details}")
        logging.error(f"[CRITICAL] sys.exc_info: {sys.exc_info()}")
        raise


@app.schedule(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False,
              use_monitor=False) 
def lead_time_collector(timer: func.TimerRequest) -> None:
    """
    Timer trigger function that runs every 5 minutes
    Collects pull request data from GitHub for lead time calculation
    PRs are linked to deployments via merge commit SHA
    """
    try:
        logging.info('[PR-COLLECTOR] Pull request collection function started.')
        
        if timer.past_due:
            logging.info('[PR-COLLECTOR] The timer is past due!')
        
        try:
            # Get GitHub access token
            logging.info('[PR-COLLECTOR] Getting GitHub access token...')
            github_token = get_github_app_token()
            logging.info('[PR-COLLECTOR] GitHub token acquired')
            
            # Collect pull request data
            logging.info('[PR-COLLECTOR] Collecting pull request data from GitHub...')
            prs = collect_github_pull_requests(github_token)
            logging.info(f"[PR-COLLECTOR] Collected {len(prs)} pull requests")
            
            # Store in SQL Database
            logging.info('[PR-COLLECTOR] Storing pull requests in database...')
            store_pull_requests(prs)
            logging.info("[PR-COLLECTOR] Pull requests stored successfully")
            
            # Generate summary
            by_repo = {}
            for pr in prs:
                repo = pr["repository"]
                by_repo[repo] = by_repo.get(repo, 0) + 1
            
            logging.info(f"[PR-COLLECTOR] Summary: {len(prs)} total PRs across {len(by_repo)} repositories")
            logging.info(f"[PR-COLLECTOR] By repository: {by_repo}")
            logging.info('[PR-COLLECTOR] Function completed successfully')
            
        except Exception as e:
            logging.error(f"[PR-COLLECTOR] Error in lead time collector: {type(e).__name__}: {str(e)}")
            import traceback
            logging.error(f"[PR-COLLECTOR] Full traceback: {traceback.format_exc()}")
            raise
    except:
        # Catch absolutely everything
        import sys
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"[PR-COLLECTOR-CRITICAL] Unhandled exception: {error_details}")
        logging.error(f"[PR-COLLECTOR-CRITICAL] sys.exc_info: {sys.exc_info()}")
        raise


@app.schedule(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False,
              use_monitor=False) 
def change_failure_rate_time_to_recover(timer: func.TimerRequest) -> None:
    """
    Timer trigger function that runs every 5 minutes
    Collects incident data from GitHub Issues for Change Failure Rate calculation
    """
    try:
        logging.info('[CFR-COLLECTOR] Starting Change Failure Rate data collection...')
        
        if timer.past_due:
            logging.info('[CFR-COLLECTOR] The timer is past due!')
        
        try:
            # Get GitHub access token
            logging.info('[CFR-COLLECTOR] Getting GitHub access token...')
            github_token = get_github_app_token()
            logging.info('[CFR-COLLECTOR] GitHub token acquired')
            
            # Collect incident data
            logging.info('[CFR-COLLECTOR] Collecting incident data from GitHub Issues...')
            incidents = collect_github_incidents(github_token)
            logging.info(f"[CFR-COLLECTOR] Collected {len(incidents)} incidents")
            
            # Store in SQL Database
            logging.info('[CFR-COLLECTOR] Storing incidents in database...')
            store_incidents(incidents)
            logging.info("[CFR-COLLECTOR] Incidents stored successfully")
            
            # Generate summary
            by_repo = {}
            by_state = {}
            for incident in incidents:
                repo = incident["repository"]
                state = incident["state"]
                by_repo[repo] = by_repo.get(repo, 0) + 1
                by_state[state] = by_state.get(state, 0) + 1
            
            logging.info(f"[CFR-COLLECTOR] Summary: {len(incidents)} total incidents across {len(by_repo)} repositories")
            logging.info(f"[CFR-COLLECTOR] By repository: {by_repo}")
            logging.info(f"[CFR-COLLECTOR] By state: {by_state}")
            logging.info('[CFR-COLLECTOR] Function completed successfully')
            
        except Exception as e:
            logging.error(f"[CFR-COLLECTOR] Error in CFR collector: {type(e).__name__}: {str(e)}")
            import traceback
            logging.error(f"[CFR-COLLECTOR] Full traceback: {traceback.format_exc()}")
            raise
    except:
        # Catch absolutely everything
        import sys
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"[CFR-COLLECTOR-CRITICAL] Unhandled exception: {error_details}")
        logging.error(f"[CFR-COLLECTOR-CRITICAL] sys.exc_info: {sys.exc_info()}")
        raise


def get_github_app_token() -> str:
    """
    Generate JWT and get installation access token for GitHub App authentication
    https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
    """
    if not GITHUB_APP_ID or not GITHUB_APP_INSTALLATION_ID or not GITHUB_APP_PRIVATE_KEY:
        raise ValueError("GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID, and GITHUB_APP_PRIVATE_KEY must be set")
    
    # Generate JWT
    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued at time (60 seconds in the past to allow for clock drift)
        "exp": now + (10 * 60),  # JWT expiration time (10 minutes)
        "iss": GITHUB_APP_ID  # GitHub App's identifier
    }
    
    # Decode private key (handle both raw and base64 encoded)
    private_key = GITHUB_APP_PRIVATE_KEY
    if not private_key.startswith("-----BEGIN"):
        # If stored as base64 in environment variable
        import base64
        private_key = base64.b64decode(private_key).decode('utf-8')
    
    # Create JWT
    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
    
    # Get installation access token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.post(
        f"https://api.github.com/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens",
        headers=headers,
        timeout=30
    )
    
    if response.status_code != 201:
        logging.error(f"Failed to get installation token: {response.status_code} - {response.text}")
        raise Exception(f"Failed to authenticate as GitHub App: {response.status_code}")
    
    token_data = response.json()
    logging.info("Successfully authenticated as GitHub App")
    return token_data["token"]


def collect_github_deployments(github_token: str) -> List[Dict[str, Any]]:
    """
    Collect deployments from GitHub organization using GraphQL API
    """
    if not GITHUB_ORG:
        raise ValueError("GITHUB_ORG_NAME must be set")
    # Parse environment filter
    environments_filter = []
    if GITHUB_DEPLOYMENT_ENVIRONMENTS:
        environments_filter = [env.strip() for env in GITHUB_DEPLOYMENT_ENVIRONMENTS.split(",") if env.strip()]
        logging.info(f"Filtering deployments for environments: {environments_filter}")
    else:
        logging.info("No environment filter set - collecting all deployment environments")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    
    # Build deployments query part with optional environment filter
    if environments_filter:
        # Convert list to GraphQL array format
        envs_graphql = '[' + ', '.join([f'"{env}"' for env in environments_filter]) + ']'
        deployments_query = f'deployments(first: 50, environments: {envs_graphql}, orderBy: {{field: CREATED_AT, direction: DESC}})'
    else:
        deployments_query = 'deployments(first: 50, orderBy: {field: CREATED_AT, direction: DESC})'
    
    # GraphQL query to get all repos and their deployments
    query = f"""
    query($org: String!, $cursor: String) {{
      organization(login: $org) {{
        repositories(first: 100, after: $cursor) {{
          pageInfo {{
            hasNextPage
            endCursor
          }}
          nodes {{
            name
            owner {{
              login
            }}
            {deployments_query} {{
              nodes {{
                id
                createdAt
                environment
                commit {{
                  oid
                  author {{
                    user {{
                      login
                    }}
                  }}
                }}
                creator {{
                  login
                }}
                latestStatus {{
                  state
                  createdAt
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    
    all_deployments = []
    cursor = None
    has_next_page = True
    
    while has_next_page:
        variables = {"org": GITHUB_ORG, "cursor": cursor}
        
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise Exception(f"GitHub API returned {response.status_code}")
        
        data = response.json()
        
        if "errors" in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            raise Exception(f"GraphQL query failed: {data['errors']}")
        
        repos = data["data"]["organization"]["repositories"]["nodes"]
        
        logging.info(f"Processing {len(repos)} repositories")
        
        for repo in repos:
            repo_name = repo["name"]
            deployments_in_repo = repo["deployments"]["nodes"]
            
            if deployments_in_repo:
                logging.info(f"Repo '{repo_name}' has {len(deployments_in_repo)} deployments")
            
            for deployment in deployments_in_repo:
                # Filter deployments from last 24 hours
                created_at = datetime.fromisoformat(deployment["createdAt"].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                hours_ago = (now - created_at).total_seconds() / 3600
                
                logging.debug(f"Deployment in {repo_name}: environment={deployment['environment']}, created={hours_ago:.1f}h ago")
                
                if hours_ago <= 24:
                    all_deployments.append({
                        "deployment_id": deployment["id"],
                        "repository": f"{repo['owner']['login']}/{repo_name}",
                        "environment": deployment["environment"],
                        "commit_sha": deployment["commit"]["oid"],
                        "created_at": deployment["createdAt"],
                        "creator": deployment["creator"]["login"] if deployment["creator"] else "unknown",
                        "status": deployment["latestStatus"]["state"] if deployment["latestStatus"] else "pending",
                        "status_updated_at": deployment["latestStatus"]["createdAt"] if deployment["latestStatus"] else None
                    })
                else:
                    logging.debug(f"Skipping deployment older than 24h: {hours_ago:.1f}h ago")
        
        page_info = data["data"]["organization"]["repositories"]["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]
    
    logging.info(f"Total deployments collected (last 24h): {len(all_deployments)}")
    return all_deployments


def collect_github_pull_requests(github_token: str) -> List[Dict[str, Any]]:
    """
    Collect merged pull requests from GitHub organization using GraphQL API
    Tracks PRs merged to the base branch (typically 'main') for lead time calculation
    """
    if not GITHUB_ORG:
        raise ValueError("GITHUB_ORG_NAME must be set")
    
    logging.info(f"Collecting merged PRs to '{BASE_BRANCH}' branch from last {PR_LOOKBACK_HOURS} hours")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    
    # Calculate time threshold (used for filtering in Python, not GraphQL)
    since_time = datetime.now(timezone.utc) - timedelta(hours=PR_LOOKBACK_HOURS)
    
    # GraphQL query to get merged PRs from all repos
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        repositories(first: 100, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            name
            owner {
              login
            }
            pullRequests(first: 50, states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}) {
              nodes {
                number
                title
                createdAt
                mergedAt
                baseRefName
                mergeCommit {
                  oid
                }
                author {
                  login
                }
              }
            }
          }
        }
      }
    }
    """
    
    all_prs = []
    cursor = None
    has_next_page = True
    
    while has_next_page:
        variables = {"org": GITHUB_ORG, "cursor": cursor}
        
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise Exception(f"GitHub API returned {response.status_code}")
        
        data = response.json()
        
        if "errors" in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            raise Exception(f"GraphQL query failed: {data['errors']}")
        
        repos = data["data"]["organization"]["repositories"]["nodes"]
        
        logging.info(f"Processing {len(repos)} repositories for PRs")
        
        for repo in repos:
            repo_name = repo["name"]
            prs_in_repo = repo["pullRequests"]["nodes"]
            
            if prs_in_repo:
                logging.info(f"Repo '{repo_name}' has {len(prs_in_repo)} merged PRs")
            
            for pr in prs_in_repo:
                # Filter by base branch and time window
                if pr["baseRefName"] != BASE_BRANCH:
                    logging.debug(f"Skipping PR #{pr['number']} - merged to {pr['baseRefName']}, not {BASE_BRANCH}")
                    continue
                
                if not pr["mergedAt"]:
                    logging.debug(f"Skipping PR #{pr['number']} - no merge timestamp")
                    continue
                
                merged_at = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                hours_ago = (datetime.now(timezone.utc) - merged_at).total_seconds() / 3600
                
                if hours_ago <= PR_LOOKBACK_HOURS:
                    all_prs.append({
                        "pr_number": pr["number"],
                        "repository": f"{repo['owner']['login']}/{repo_name}",
                        "title": pr["title"],
                        "author": pr["author"]["login"] if pr["author"] else "unknown",
                        "created_at": pr["createdAt"],
                        "merged_at": pr["mergedAt"],
                        "merge_commit_sha": pr["mergeCommit"]["oid"] if pr["mergeCommit"] else None,
                        "base_branch": pr["baseRefName"]
                    })
                    logging.debug(f"Added PR #{pr['number']} from {repo_name}, merged {hours_ago:.1f}h ago")
                else:
                    logging.debug(f"Skipping PR #{pr['number']} - merged {hours_ago:.1f}h ago (outside {PR_LOOKBACK_HOURS}h window)")
        
        page_info = data["data"]["organization"]["repositories"]["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]
    
    logging.info(f"Total PRs collected (merged to {BASE_BRANCH} in last {PR_LOOKBACK_HOURS}h): {len(all_prs)}")
    return all_prs


def collect_github_incidents(github_token: str) -> List[Dict[str, Any]]:
    """
    Collect incidents from GitHub Issues with labels "incident" AND "production"
    Uses GraphQL API to query organization repositories
    """
    if not GITHUB_ORG:
        raise ValueError("GITHUB_ORG_NAME must be set")
    
    since_time = datetime.now(timezone.utc) - timedelta(hours=INCIDENT_LOOKBACK_HOURS)
    logging.info(f"Collecting incidents from last {INCIDENT_LOOKBACK_HOURS} hours (since {since_time.isoformat()})")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # GraphQL query to get all repos and their issues with incident labels
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        repositories(first: 100, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            name
            owner {
              login
            }
            issues(first: 50, labels: ["incident", "production"], states: [OPEN, CLOSED], orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes {
                number
                title
                bodyText
                createdAt
                closedAt
                state
                labels(first: 20) {
                  nodes {
                    name
                  }
                }
                author {
                  login
                }
                url
              }
            }
          }
        }
      }
    }
    """
    
    all_incidents = []
    cursor = None
    has_next_page = True
    
    while has_next_page:
        variables = {"org": GITHUB_ORG, "cursor": cursor}
        
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise Exception(f"GitHub API returned {response.status_code}")
        
        data = response.json()
        
        if "errors" in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            raise Exception(f"GraphQL query failed: {data['errors']}")
        
        repos = data["data"]["organization"]["repositories"]["nodes"]
        
        logging.info(f"Processing {len(repos)} repositories for incidents")
        
        for repo in repos:
            repo_name = repo["name"]
            issues_in_repo = repo["issues"]["nodes"]
            
            if issues_in_repo:
                logging.info(f"Repo '{repo_name}' has {len(issues_in_repo)} issues with incident+production labels")
            
            for issue in issues_in_repo:
                # Filter by time window
                created_at = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
                hours_ago = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                
                logging.debug(f"Issue #{issue['number']} in {repo_name}: created {hours_ago:.1f}h ago")
                
                if hours_ago <= INCIDENT_LOOKBACK_HOURS:
                    # Verify both "incident" and "production" labels are present
                    label_names = [label["name"].lower() for label in issue["labels"]["nodes"]]
                    has_incident_label = any(label in ["incident", "production-incident"] for label in label_names)
                    has_production_label = any(label in ["production", "environment:production", "env:production"] for label in label_names)
                    
                    if has_incident_label and has_production_label:
                        # Extract product from issue body
                        import re
                        product = None
                        if issue.get("bodyText"):
                            # Parse product using regex pattern from GitHub issue form
                            product_match = re.search(r'### Product Affected\s*\n\s*(.+)', issue["bodyText"])
                            if product_match:
                                product = product_match.group(1).strip()
                                logging.debug(f"Extracted product '{product}' from issue #{issue['number']}")
                            else:
                                logging.debug(f"No product field found in issue #{issue['number']} body")
                        
                        # Convert labels list to JSON string
                        import json
                        labels_json = json.dumps([label["name"] for label in issue["labels"]["nodes"]])
                        
                        all_incidents.append({
                            "issue_number": issue["number"],
                            "repository": f"{repo['owner']['login']}/{repo_name}",
                            "title": issue["title"],
                            "created_at": issue["createdAt"],
                            "closed_at": issue["closedAt"],
                            "state": issue["state"].lower(),
                            "labels": labels_json,
                            "product": product,
                            "creator": issue["author"]["login"] if issue["author"] else "unknown",
                            "url": issue["url"]
                        })
                        logging.debug(f"Added incident #{issue['number']} from {repo_name}, created {hours_ago:.1f}h ago, product={product}")
                    else:
                        logging.debug(f"Skipping issue #{issue['number']} - missing required labels (incident={has_incident_label}, production={has_production_label})")
                else:
                    logging.debug(f"Skipping issue #{issue['number']} - created {hours_ago:.1f}h ago (outside {INCIDENT_LOOKBACK_HOURS}h window)")
        
        page_info = data["data"]["organization"]["repositories"]["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]
    
    logging.info(f"Total incidents collected (last {INCIDENT_LOOKBACK_HOURS}h): {len(all_incidents)}")
    return all_incidents


def get_repository_teams(github_token: str, owner: str, repo: str) -> Optional[str]:
    """Fetch team names for a repository from GitHub API"""
    try:
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/teams",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            teams = response.json()
            if teams:
                team_names = [team['name'] for team in teams]
                return ', '.join(team_names)
            return None
        elif response.status_code == 404:
            logging.debug(f"No teams found for {owner}/{repo} (404)")
            return None
        else:
            logging.warning(f"Failed to fetch teams for {owner}/{repo}: {response.status_code}")
            return None
    except Exception as e:
        logging.warning(f"Error fetching teams for {owner}/{repo}: {type(e).__name__}: {str(e)}")
        return None

def update_daily_metrics(cursor, conn):
    """Calculate and update daily deployment metrics by aggregating deployment data"""
    try:
        logging.info("[update_daily_metrics] Calculating daily metrics from deployments...")
        
        # Aggregate metrics for today using MERGE to handle updates
        merge_query = """
        MERGE INTO deployment_metrics_daily AS target
        USING (
            SELECT 
                CAST(created_at AS DATE) as deployment_date,
                repository,
                environment,
                COUNT(*) as total_deployments,
                SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_deployments,
                SUM(CASE WHEN status IN ('FAILURE', 'ERROR') THEN 1 ELSE 0 END) as failed_deployments
            FROM deployments
            WHERE created_at >= DATEADD(day, -1, GETUTCDATE())
            GROUP BY CAST(created_at AS DATE), repository, environment
        ) AS source
        ON target.date = source.deployment_date 
            AND target.repository = source.repository 
            AND target.environment = source.environment
        WHEN MATCHED THEN
            UPDATE SET 
                total_deployments = source.total_deployments,
                successful_deployments = source.successful_deployments,
                failed_deployments = source.failed_deployments,
                calculated_at = GETUTCDATE()
        WHEN NOT MATCHED THEN
            INSERT (date, repository, environment, total_deployments, successful_deployments, failed_deployments, calculated_at)
            VALUES (source.deployment_date, source.repository, source.environment, 
                    source.total_deployments, source.successful_deployments, source.failed_deployments, GETUTCDATE());
        """
        
        cursor.execute(merge_query)
        conn.commit()
        
        # Get count of updated metrics
        cursor.execute("SELECT COUNT(*) FROM deployment_metrics_daily WHERE calculated_at >= DATEADD(minute, -1, GETUTCDATE())")
        metrics_count = cursor.fetchone()[0]
        logging.info(f"[update_daily_metrics] Successfully updated {metrics_count} daily metric records")
        
    except Exception as e:
        logging.error(f"[update_daily_metrics] Error updating metrics: {type(e).__name__}: {str(e)}")
        raise


def store_deployments(deployments: List[Dict[str, Any]], github_token: Optional[str] = None) -> None:
    """
    Store deployment data in Azure SQL Database using Entra ID authentication
    """
    logging.info(f"[store_deployments] Starting to store {len(deployments)} deployments")
    
    if not deployments:
        logging.info("No deployments to store")
        return
    
    conn = None
    cursor = None
    
    try:
        # Get access token for SQL Database using Managed Identity
        logging.info("[store_deployments] Getting access token for SQL Database...")
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        logging.info("[store_deployments] Access token acquired successfully")
        
        # List available ODBC drivers
        logging.info("[store_deployments] Checking available ODBC drivers...")
        try:
            available_drivers = [driver for driver in pyodbc.drivers()]
            logging.info(f"[store_deployments] Available ODBC drivers: {available_drivers}")
        except Exception as driver_error:
            logging.warning(f"[store_deployments] Could not list ODBC drivers: {driver_error}")
        
        # Connection string for Entra ID authentication
        connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SQL_SERVER},1433;Database={SQL_DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
        logging.info(f"[store_deployments] Connecting to SQL Server: {SQL_SERVER}, Database: {SQL_DATABASE}")
        
        # SQL_COPT_SS_ACCESS_TOKEN constant for pyodbc
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        
        # Encode the token properly with length prefix using struct
        # This is required for Azure SQL token-based authentication
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        logging.info(f"[store_deployments] Token encoded and packed, length: {len(token_struct)} bytes")
        
        # Attempt connection
        logging.info("[store_deployments] Attempting pyodbc.connect()...")
        print("[DEBUG] About to call pyodbc.connect()")
        try:
            conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            print("[DEBUG] pyodbc.connect() returned successfully")
            logging.info("[store_deployments] Database connection established successfully")
        except pyodbc.Error as pyo_err:
            print(f"[DEBUG] pyodbc.Error caught: {pyo_err}")
            logging.error(f"[store_deployments] pyodbc.Error: {pyo_err}")
            for arg in pyo_err.args:
                logging.error(f"[store_deployments] Error arg: {arg}")
            raise
        except Exception as conn_ex:
            print(f"[DEBUG] Exception caught: {type(conn_ex).__name__}: {conn_ex}")
            logging.error(f"[store_deployments] Connection exception: {type(conn_ex).__name__}: {conn_ex}")
            raise
        
        cursor = conn.cursor()
        print("[DEBUG] Cursor created successfully")
        logging.info("[store_deployments] Database cursor created")
        
        # Auto-populate repositories table with team information
        logging.info("[store_deployments] Ensuring repositories are registered...")
        unique_repos = set(d['repository'] for d in deployments)
        repo_insert_query = """
        MERGE INTO repositories AS target
        USING (SELECT ? AS name, ? AS team) AS source
        ON target.name = source.name
        WHEN MATCHED AND target.team IS NULL AND source.team IS NOT NULL THEN
            UPDATE SET team = source.team, updated_at = GETUTCDATE()
        WHEN NOT MATCHED THEN
            INSERT (name, team, is_active, created_at, updated_at)
            VALUES (?, ?, 1, GETUTCDATE(), GETUTCDATE());
        """
        
        for repo in unique_repos:
            team_name = None
            if github_token:
                # Parse owner/repo from full name
                parts = repo.split('/')
                if len(parts) == 2:
                    owner, repo_name = parts
                    logging.info(f"[store_deployments] Fetching teams for {repo}...")
                    team_name = get_repository_teams(github_token, owner, repo_name)
                    if team_name:
                        logging.info(f"[store_deployments] Found teams for {repo}: {team_name}")
            
            cursor.execute(repo_insert_query, repo, team_name, repo, team_name)
        
        conn.commit()
        logging.info(f"[store_deployments] Registered {len(unique_repos)} repositories")
        
        # Insert deployments (ignore duplicates)
        logging.info("[store_deployments] Preparing to insert deployments...")
        insert_query = """
        MERGE INTO deployments AS target
        USING (SELECT ? AS deployment_id) AS source
        ON target.deployment_id = source.deployment_id
        WHEN NOT MATCHED THEN
            INSERT (deployment_id, repository, environment, commit_sha, created_at, creator, status, status_updated_at, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        inserted_count = 0
        for idx, deployment in enumerate(deployments, 1):
            try:
                logging.info(f"[store_deployments] Inserting deployment {idx}/{len(deployments)}: {deployment['deployment_id']}")
                cursor.execute(insert_query, 
                    deployment["deployment_id"],
                    deployment["deployment_id"],
                    deployment["repository"],
                    deployment["environment"],
                    deployment["commit_sha"],
                    deployment["created_at"],
                    deployment["creator"],
                    deployment["status"],
                    deployment["status_updated_at"],
                    datetime.now(timezone.utc).isoformat()
                )
                inserted_count += 1
            except Exception as insert_error:
                logging.error(f"[store_deployments] Error inserting deployment {deployment['deployment_id']}: {type(insert_error).__name__}: {str(insert_error)}")
                raise
        
        logging.info(f"[store_deployments] Committing transaction with {inserted_count} deployments...")
        conn.commit()
        logging.info(f"[store_deployments] Successfully stored {inserted_count} deployments")
        
        # Verify records were inserted
        cursor.execute("SELECT COUNT(*) FROM deployments WHERE collected_at >= DATEADD(minute, -5, GETUTCDATE())")
        result = cursor.fetchone()
        count = result[0] if result else 0
        logging.info(f"[store_deployments] VERIFICATION: {count} records found in deployments table from last 5 minutes")
        
        # Update daily metrics
        logging.info("[store_deployments] Updating daily metrics...")
        update_daily_metrics(cursor, conn)
        
    except Exception as e:
        logging.error(f"[store_deployments] Database error: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"[store_deployments] Traceback: {traceback.format_exc()}")
        if conn:
            try:
                conn.rollback()
                logging.info("[store_deployments] Transaction rolled back")
            except:
                logging.error("[store_deployments] Error during rollback")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
                logging.info("[store_deployments] Cursor closed")
            except Exception as cleanup_error:
                logging.error(f"[store_deployments] Error closing cursor: {type(cleanup_error).__name__}: {str(cleanup_error)}")
        if conn:
            try:
                conn.close()
                logging.info("[store_deployments] Connection closed")
            except Exception as cleanup_error:
                logging.error(f"[store_deployments] Error closing connection: {type(cleanup_error).__name__}: {str(cleanup_error)}")


def generate_summary(deployments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics for the collected deployments
    """
    if not deployments:
        return {"total": 0}
    
    summary = {
        "total": len(deployments),
        "by_repository": {},
        "by_status": {},
        "successful": 0,
        "failed": 0
    }
    
    for deployment in deployments:
        repo = deployment["repository"]
        status = deployment["status"]
        
        summary["by_repository"][repo] = summary["by_repository"].get(repo, 0) + 1
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        
        if status and status.upper() == "SUCCESS":
            summary["successful"] += 1
        elif status and status.upper() == "FAILURE":
            summary["failed"] += 1
    
    return summary


def store_pull_requests(prs: List[Dict[str, Any]]) -> None:
    """
    Store pull request data in Azure SQL Database using Entra ID authentication
    PRs are linked to deployments via merge_commit_sha for lead time calculation
    """
    logging.info(f"[store_pull_requests] Starting to store {len(prs)} pull requests")
    
    if not prs:
        logging.info("[store_pull_requests] No pull requests to store")
        return
    
    # Filter out PRs without merge commit SHA
    valid_prs = [pr for pr in prs if pr.get("merge_commit_sha")]
    if len(valid_prs) < len(prs):
        logging.warning(f"[store_pull_requests] Filtered out {len(prs) - len(valid_prs)} PRs without merge commit SHA")
    
    if not valid_prs:
        logging.info("[store_pull_requests] No valid pull requests to store")
        return
    
    conn = None
    cursor = None
    
    try:
        # Get access token for SQL Database using Managed Identity
        logging.info("[store_pull_requests] Getting access token for SQL Database...")
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        logging.info("[store_pull_requests] Access token acquired successfully")
        
        # Connection string for Entra ID authentication
        connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SQL_SERVER},1433;Database={SQL_DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
        logging.info(f"[store_pull_requests] Connecting to SQL Server: {SQL_SERVER}, Database: {SQL_DATABASE}")
        
        # SQL_COPT_SS_ACCESS_TOKEN constant for pyodbc
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        
        # Encode the token properly with length prefix using struct
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        logging.info(f"[store_pull_requests] Token encoded and packed, length: {len(token_struct)} bytes")
        
        # Attempt connection
        logging.info("[store_pull_requests] Attempting pyodbc.connect()...")
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        logging.info("[store_pull_requests] Database connection established successfully")
        
        cursor = conn.cursor()
        logging.info("[store_pull_requests] Database cursor created")
        
        # Insert pull requests using MERGE for idempotent upserts
        logging.info("[store_pull_requests] Preparing to insert pull requests...")
        merge_query = """
        MERGE INTO pull_requests AS target
        USING (SELECT ? AS repository, ? AS pr_number) AS source
        ON target.repository = source.repository AND target.pr_number = source.pr_number
        WHEN MATCHED THEN
            UPDATE SET 
                title = ?,
                author = ?,
                merged_at = ?,
                merge_commit_sha = ?,
                base_branch = ?,
                collected_at = ?
        WHEN NOT MATCHED THEN
            INSERT (pr_number, repository, title, author, created_at, merged_at, merge_commit_sha, base_branch, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        inserted_count = 0
        for idx, pr in enumerate(valid_prs, 1):
            try:
                logging.debug(f"[store_pull_requests] Processing PR {idx}/{len(valid_prs)}: {pr['repository']}#{pr['pr_number']}")
                cursor.execute(merge_query,
                    # USING clause
                    pr["repository"],
                    pr["pr_number"],
                    # WHEN MATCHED UPDATE
                    pr["title"],
                    pr["author"],
                    pr["merged_at"],
                    pr["merge_commit_sha"],
                    pr["base_branch"],
                    datetime.now(timezone.utc).isoformat(),
                    # WHEN NOT MATCHED INSERT
                    pr["pr_number"],
                    pr["repository"],
                    pr["title"],
                    pr["author"],
                    pr["created_at"],
                    pr["merged_at"],
                    pr["merge_commit_sha"],
                    pr["base_branch"],
                    datetime.now(timezone.utc).isoformat()
                )
                inserted_count += 1
            except Exception as insert_error:
                logging.error(f"[store_pull_requests] Error inserting PR {pr['repository']}#{pr['pr_number']}: {type(insert_error).__name__}: {str(insert_error)}")
                raise
        
        logging.info(f"[store_pull_requests] Committing transaction with {inserted_count} pull requests...")
        conn.commit()
        logging.info(f"[store_pull_requests] Successfully stored {inserted_count} pull requests")
        
        # Verify records were inserted
        cursor.execute("SELECT COUNT(*) FROM pull_requests WHERE collected_at >= DATEADD(minute, -5, GETUTCDATE())")
        result = cursor.fetchone()
        count = result[0] if result else 0
        logging.info(f"[store_pull_requests] VERIFICATION: {count} records found in pull_requests table from last 5 minutes")
        
        # Log correlation stats
        cursor.execute("""
            SELECT COUNT(DISTINCT pr.id) as pr_count, 
                   COUNT(DISTINCT d.id) as deployment_count,
                   COUNT(DISTINCT pr.merge_commit_sha) as unique_commits
            FROM pull_requests pr
            LEFT JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
            WHERE pr.collected_at >= DATEADD(hour, -1, GETUTCDATE())
        """)
        stats = cursor.fetchone()
        if stats:
            logging.info(f"[store_pull_requests] CORRELATION: {stats[0]} PRs, {stats[1]} matching deployments, {stats[2]} unique commits in last hour")
        else:
            logging.info("[store_pull_requests] CORRELATION: No correlation data available")
        
    except Exception as e:
        logging.error(f"[store_pull_requests] Database error: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"[store_pull_requests] Traceback: {traceback.format_exc()}")
        if conn:
            try:
                conn.rollback()
                logging.info("[store_pull_requests] Transaction rolled back")
            except:
                logging.error("[store_pull_requests] Error during rollback")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
                logging.debug("[store_pull_requests] Cursor closed")
            except Exception as cleanup_error:
                logging.error(f"[store_pull_requests] Error closing cursor: {type(cleanup_error).__name__}: {str(cleanup_error)}")
        if conn:
            try:
                conn.close()
                logging.debug("[store_pull_requests] Connection closed")
            except Exception as cleanup_error:
                logging.error(f"[store_pull_requests] Error closing connection: {type(cleanup_error).__name__}: {str(cleanup_error)}")


def store_incidents(incidents: List[Dict[str, Any]]) -> None:
    """
    Store incident data in Azure SQL Database using Entra ID authentication
    Incidents are GitHub Issues with labels "incident" AND "production"
    """
    logging.info(f"[store_incidents] Starting to store {len(incidents)} incidents")
    
    if not incidents:
        logging.info("[store_incidents] No incidents to store")
        return
    
    conn = None
    cursor = None
    
    try:
        # Get access token for SQL Database using Managed Identity
        logging.info("[store_incidents] Getting access token for SQL Database...")
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        logging.info("[store_incidents] Access token acquired successfully")
        
        # Connection string for Entra ID authentication
        connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SQL_SERVER},1433;Database={SQL_DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
        logging.info(f"[store_incidents] Connecting to SQL Server: {SQL_SERVER}, Database: {SQL_DATABASE}")
        
        # SQL_COPT_SS_ACCESS_TOKEN constant for pyodbc
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        
        # Encode the token properly with length prefix using struct
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        logging.info(f"[store_incidents] Token encoded and packed, length: {len(token_struct)} bytes")
        
        # Attempt connection
        logging.info("[store_incidents] Attempting pyodbc.connect()...")
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        logging.info("[store_incidents] Database connection established successfully")
        
        cursor = conn.cursor()
        logging.info("[store_incidents] Database cursor created")
        
        # Insert incidents using MERGE for idempotent upserts
        logging.info("[store_incidents] Preparing to insert incidents...")
        merge_query = """
        MERGE INTO incidents AS target
        USING (SELECT ? AS repository, ? AS issue_number) AS source
        ON target.repository = source.repository AND target.issue_number = source.issue_number
        WHEN MATCHED THEN
            UPDATE SET 
                title = ?,
                closed_at = ?,
                state = ?,
                labels = ?,
                product = ?,
                creator = ?,
                url = ?,
                collected_at = ?
        WHEN NOT MATCHED THEN
            INSERT (issue_number, repository, title, created_at, closed_at, state, labels, product, creator, url, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        inserted_count = 0
        for idx, incident in enumerate(incidents, 1):
            try:
                logging.debug(f"[store_incidents] Processing incident {idx}/{len(incidents)}: {incident['repository']}#{incident['issue_number']}")
                cursor.execute(merge_query,
                    # USING clause
                    incident["repository"],
                    incident["issue_number"],
                    # WHEN MATCHED UPDATE
                    incident["title"],
                    incident["closed_at"],
                    incident["state"],
                    incident["labels"],
                    incident.get("product"),
                    incident["creator"],
                    incident["url"],
                    datetime.now(timezone.utc).isoformat(),
                    # WHEN NOT MATCHED INSERT
                    incident["issue_number"],
                    incident["repository"],
                    incident["title"],
                    incident["created_at"],
                    incident["closed_at"],
                    incident["state"],
                    incident["labels"],
                    incident.get("product"),
                    incident["creator"],
                    incident["url"],
                    datetime.now(timezone.utc).isoformat()
                )
                inserted_count += 1
            except Exception as insert_error:
                logging.error(f"[store_incidents] Error inserting incident {incident['repository']}#{incident['issue_number']}: {type(insert_error).__name__}: {str(insert_error)}")
                raise
        
        logging.info(f"[store_incidents] Committing transaction with {inserted_count} incidents...")
        conn.commit()
        logging.info(f"[store_incidents] Successfully stored {inserted_count} incidents")
        
        # Verify records were inserted
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE collected_at >= DATEADD(minute, -5, GETUTCDATE())")
        result = cursor.fetchone()
        count = result[0] if result else 0
        logging.info(f"[store_incidents] VERIFICATION: {count} records found in incidents table from last 5 minutes")
        
        # Log correlation preview stats (deployments with incidents in 24h window)
        cursor.execute("""
            SELECT COUNT(DISTINCT d.id) as deployment_count,
                   COUNT(DISTINCT i.id) as incident_count
            FROM deployments d
            LEFT JOIN incidents i 
                ON d.repository = i.repository
                AND i.created_at >= d.created_at
                AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
            WHERE d.created_at >= DATEADD(day, -1, GETUTCDATE())
        """)
        stats = cursor.fetchone()
        if stats:
            logging.info(f"[store_incidents] CORRELATION PREVIEW: {stats[0]} deployments, {stats[1]} incidents in last 24h")
        else:
            logging.info("[store_incidents] CORRELATION PREVIEW: No correlation data available")
        
    except Exception as e:
        logging.error(f"[store_incidents] Database error: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"[store_incidents] Traceback: {traceback.format_exc()}")
        if conn:
            try:
                conn.rollback()
                logging.info("[store_incidents] Transaction rolled back")
            except:
                logging.error("[store_incidents] Error during rollback")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
                logging.debug("[store_incidents] Cursor closed")
            except Exception as cleanup_error:
                logging.error(f"[store_incidents] Error closing cursor: {type(cleanup_error).__name__}: {str(cleanup_error)}")
        if conn:
            try:
                conn.close()
                logging.debug("[store_incidents] Connection closed")
            except Exception as cleanup_error:
                logging.error(f"[store_incidents] Error closing connection: {type(cleanup_error).__name__}: {str(cleanup_error)}")


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint
    """
    return func.HttpResponse(
        '{"status": "healthy", "service": "deployment-frequency-collector"}',
        status_code=200,
        mimetype="application/json"
    )
