# Crea una estructura VACIA sin sobrescribir archivos existentes.
# El ZIP ya incluye el codigo completo. Este script es para aprender el proceso.
$root = $PSScriptRoot
$directories = @(
    'backend/app/api', 'backend/app/agents', 'backend/app/orchestration',
    'backend/app/tools', 'backend/app/prompts', 'backend/app/services',
    'backend/app/schemas', 'backend/app/core', 'backend/tests',
    'frontend/src/components', 'frontend/src/services'
)
foreach ($dir in $directories) {
    New-Item -ItemType Directory -Path (Join-Path $root $dir) -Force | Out-Null
}
$files = @(
    '.gitignore', 'backend/requirements.txt', 'backend/.env.example',
    'backend/app/__init__.py', 'backend/app/main.py',
    'backend/app/api/__init__.py','backend/app/api/chat.py',
    'backend/app/agents/__init__.py','backend/app/agents/factory.py','backend/app/agents/policy_agent.py',
    'backend/app/agents/orchestrator.py','backend/app/agents/comfort_agent.py',
    'backend/app/agents/consumption_agent.py','backend/app/agents/economy_agent.py',
    'backend/app/orchestration/__init__.py','backend/app/orchestration/workflow.py',
    'backend/app/tools/__init__.py','backend/app/tools/azure_search.py',
    'backend/app/core/__init__.py','backend/app/core/config.py',
    'backend/app/services/__init__.py','backend/app/services/costs.py',
    'backend/app/services/security.py','backend/app/services/audit.py','backend/app/services/rate_limit.py',
    'backend/app/schemas/__init__.py','backend/app/schemas/models.py',
    'backend/app/prompts/orchestrator.md','backend/app/prompts/policy.md','backend/app/prompts/comfort.md',
    'backend/app/prompts/consumption.md','backend/app/prompts/economy.md',
    'backend/tests/test_costs.py','backend/tests/test_security.py',
    'frontend/package.json','frontend/vite.config.js',
    'frontend/index.html','frontend/src/main.jsx','frontend/src/App.jsx',
    'frontend/src/styles.css','frontend/src/services/api.js',
    'frontend/src/components/AgentGraph.jsx',
    'frontend/src/components/CostPanel.jsx',
    'frontend/src/components/EventLog.jsx','README.md'
)
foreach ($file in $files) {
    $path = Join-Path $root $file
    if (-not (Test-Path $path)) {
        New-Item -ItemType File -Path $path -Force | Out-Null
    }
}
Write-Host "Estructura creada o verificada en: $root"
