package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sort"
	"time"
)

// NHI = Non-Human Identity (machine identity in the cloud).
type NHI struct {
	ID          string   `json:"id"`
	Source      string   `json:"source"` // aws | github | k8s | gcp | azure
	Name        string   `json:"name"`
	Scope       string   `json:"scope"`
	Perms       []string `json:"perms"`
	LastUsed    string   `json:"last_used"` // RFC3339
	Owner       string   `json:"owner"`
	ExpiresAt   string   `json:"expires_at"` // RFC3339 (empty = never)
	PublicLeak  bool     `json:"public_leak"` // leaked key/token in a public repo
	Hardcoded   bool     `json:"hardcoded"`   // secret hardcoded in config
}

type RiskLevel string

const (
	Critical RiskLevel = "CRITICAL"
	High     RiskLevel = "HIGH"
	Medium   RiskLevel = "MEDIUM"
	Low      RiskLevel = "LOW"
)

type ScoredNHI struct {
	NHI        NHI       `json:"nhi"`
	Risk       RiskLevel `json:"risk"`
	Score      int       `json:"score"` // 0-100
	Reasons    []string  `json:"reasons"`
	Proposed   []string  `json:"proposed"`   // proposed remediation actions
	ApprovedID string    `json:"approved_id"` // set when a human approves
}

// ---- connectors (mock) ----
var mockInventory = []NHI{
	{ID: "aws-001", Source: "aws", Name: "deploy-key-prod", Scope: "prod",
		Perms: []string{"s3:PutObject", "ec2:RunInstances"}, Owner: "team-deploy",
		LastUsed: "2026-04-01T00:00:00Z"}, // ! unused ~150d
	{ID: "aws-002", Source: "aws", Name: "ci-runner-role", Scope: "ci",
		Perms: []string{"eks:Describe*", "iam:List*", "s3:PutObject", "ssm:PutParameter", "ecr:*"},
		Owner: "platform", LastUsed: "2026-08-29T00:00:00Z",
		ExpiresAt: ""}, // over-privileged (broad)
	{ID: "gh-001", Source: "github", Name: "github-app-billing-tokens", Scope: "org",
		Perms: []string{"repo", "admin:org"}, PublicLeak: true,
		LastUsed: "2026-08-20T00:00:00Z"}, // ! leaked in public repo
	{ID: "k8s-001", Source: "k8s", Name: "payment-svc-serviceaccount", Scope: "payment",
		Perms: []string{"secrets:get"}, Owner: "team-payment",
		LastUsed: "2026-08-30T00:00:00Z",
		ExpiresAt: "2026-09-15T00:00:00Z"}, // ! cert expires < 30d
	{ID: "aws-003", Source: "aws", Name: "backup-role", Scope: "backups",
		Perms: []string{"s3:ListBucket", "s3:GetObject"}, Owner: "team-ops",
		LastUsed: "2026-08-28T00:00:00Z", Hardcoded: true}, // hardcoded secret
	{ID: "k8s-002", Source: "k8s", Name: "grafana-dashboard-sa", Scope: "monitoring",
		Perms: []string{"get:deployments"}, Owner: "team-observ",
		LastUsed: "2026-08-31T00:00:00Z"}, // healthy
}

// ---- risk engine ----
func daysSince(ts string) int {
	t, err := time.Parse(time.RFC3339, ts)
	if err != nil {
		return 0
	}
	return int(time.Since(t).Hours() / 24)
}

func daysUntil(ts string) int {
	if ts == "" {
		return 1 << 30 // never expires
	}
	t, err := time.Parse(time.RFC3339, ts)
	if err != nil {
		return 1 << 30
	}
	return int(time.Until(t).Hours() / 24)
}

func score(n NHI) ScoredNHI {
	s := ScoredNHI{NHI: n}
	s.Reasons = []string{}
	s.Proposed = []string{}

	// Unused
	if d := daysSince(n.LastUsed); d > 90 {
		s.Score += 40
		s.Reasons = append(s.Reasons, fmt.Sprintf("unused %d days", d))
		s.Proposed = append(s.Proposed, "decommission (human approval)")
	} else if d > 30 {
		s.Score += 15
		s.Reasons = append(s.Reasons, fmt.Sprintf("low activity %d days", d))
	}

	// Over-privileged (heuristic: >3 broad write/admin perms)
	permissionCount := len(n.Perms)
	if permissionCount >= 5 {
		s.Score += 25
		s.Reasons = append(s.Reasons, "over-privileged (broad permission set)")
		s.Proposed = append(s.Proposed, "apply least-privilege policy patch")
	}

	// Public leak -> critical
	if n.PublicLeak {
		s.Score += 60
		s.Reasons = append(s.Reasons, "key/token leaked in public repo (CRITICAL)")
		s.Proposed = append(s.Proposed, "rotate token immediately + revoke+audit")
	}

	// Hardcoded secret
	if n.Hardcoded {
		s.Score += 35
		s.Reasons = append(s.Reasons, "secret hardcoded in config")
		s.Proposed = append(s.Proposed, "move to secrets manager / vault")
	}

	// Expiring
	if d := daysUntil(n.ExpiresAt); d > 0 && d < 30 {
		s.Score += 45
		s.Reasons = append(s.Reasons, fmt.Sprintf("credential expires in %d days", d))
		s.Proposed = append(s.Proposed, fmt.Sprintf("rotate before %s", n.ExpiresAt[:10]))
	}

	// Orphaned (no owner)
	if n.Owner == "" {
		s.Score += 20
		s.Reasons = append(s.Reasons, "orphaned (no owner)")
		s.Proposed = append(s.Proposed, "assign owner or decommission")
	}

	// level + clamp
	switch {
	case s.Score >= 80:
		s.Risk = Critical
	case s.Score >= 50:
		s.Risk = High
	case s.Score >= 25:
		s.Risk = Medium
	default:
		s.Risk = Low
	}
	if s.Score > 100 {
		s.Score = 100
	}
	return s
}

// ---- report ----
func renderReport(results []ScoredNHI) string {
	sort.Slice(results, func(i, j int) bool { return results[i].Score > results[j].Score })
	out := "ARCHIVE: NHI-Governance Risk Report\n"
	out += fmt.Sprintf("Generated: %s\n", time.Now().UTC().Format(time.RFC3339))
	out += "------------------------------------------------------\n\n"
	for _, r := range results {
		icon := map[RiskLevel]string{Critical: "🔴", High: "🟠", Medium: "🟡", Low: "🟢"}[r.Risk]
		out += fmt.Sprintf("%s [%s] %s (%s/%s) score=%d\n", icon, r.Risk, r.NHI.Name, r.NHI.Source, r.NHI.Scope, r.Score)
		for _, why := range r.Reasons {
			out += fmt.Sprintf("    - %s\n", why)
		}
		for _, p := range r.Proposed {
			status := "PENDING"
			if r.ApprovedID == r.NHI.ID {
				status = "APPROVED"
			}
			out += fmt.Sprintf("    • PROPOSE:%s [%s]\n", p, status)
		}
		out += "\n"
	}
	return out
}

// ---- human-in-the-loop approval (mock CLI) ----
func approve(report string, id string) {
	// In the real agent this is a Slack/chat/UI approval gate.
	// Here: write APPROVED state for the matching NHI.
	fmt.Printf("\n>>> Human approved remediation for %s <<<\n", id)
}

func main() {
	mode := "report"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	results := make([]ScoredNHI, 0, len(mockInventory))
	for _, n := range mockInventory {
		results = append(results, score(n))
	}

	switch mode {
	case "report", "":
		fmt.Print(renderReport(results))
		js, _ := json.MarshalIndent(results, "", "  ")
		os.WriteFile("inventory_scored.json", js, 0644)
		fmt.Println("(also wrote inventory_scored.json)")
	case "approve":
		if len(os.Args) < 3 {
			log.Fatal("usage: shield-nhi approve <nhi-id>")
		}
		// Demonstrates the approval gate: re-run, mark approved.
		for i := range results {
			if results[i].NHI.ID == os.Args[2] {
				results[i].ApprovedID = os.Args[2]
			}
		}
		approve(renderReport(results), os.Args[2])
		fmt.Print(renderReport(results))
	default:
		log.Fatalf("unknown mode %q (use: report | approve)", mode)
	}
}