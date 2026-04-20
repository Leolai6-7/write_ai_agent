# 🌿 分支開發策略

## 分支結構

```
main (生產分支)
├── develop (開發主分支)
│   ├── feature/volume-system (功能分支)
│   ├── feature/context-builder (功能分支)
│   ├── feature/batch-generation (功能分支)
│   └── hotfix/api-quota-handling (緊急修復)
└── release/v3.0.0 (發布分支)
```

## 分支說明

### 🚀 main (生產分支)
- **用途**: 穩定的生產版本
- **保護**: 只能通過 PR 合併
- **部署**: 自動部署到生產環境
- **版本**: 對應正式發布版本

### 🔧 develop (開發主分支)  
- **用途**: 集成所有功能開發
- **來源**: 從 main 分支創建
- **合併**: 接收所有 feature 分支
- **測試**: 完整的功能測試

### ✨ feature/* (功能分支)
- **命名**: `feature/功能名稱`
- **來源**: 從 develop 分支創建
- **用途**: 開發單一功能或特性
- **合併**: 完成後合併回 develop

### 🔥 hotfix/* (緊急修復)
- **命名**: `hotfix/問題描述`
- **來源**: 從 main 分支創建
- **用途**: 修復生產環境緊急問題
- **合併**: 同時合併到 main 和 develop

### 📦 release/* (發布分支)
- **命名**: `release/版本號`
- **來源**: 從 develop 分支創建
- **用途**: 準備發布版本
- **合併**: 測試完成後合併到 main

## 工作流程

### 🔄 功能開發流程
```bash
# 1. 從 develop 創建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/new-agent-system

# 2. 開發功能
# ... 進行開發工作 ...

# 3. 提交並推送
git add .
git commit -m "feat: 添加新的代理系統"
git push -u origin feature/new-agent-system

# 4. 創建 Pull Request
# 在 GitHub 上創建 PR: feature/new-agent-system -> develop

# 5. 代碼審查和合併
# 經過審查後合併到 develop
```

### 🚀 發布流程
```bash
# 1. 從 develop 創建發布分支
git checkout develop
git checkout -b release/v3.1.0

# 2. 版本準備工作
# - 更新版本號
# - 更新 CHANGELOG
# - 最終測試

# 3. 合併到 main
git checkout main
git merge release/v3.1.0
git tag v3.1.0
git push origin main --tags

# 4. 合併回 develop
git checkout develop
git merge release/v3.1.0
git push origin develop
```

## 提交信息規範

### 格式
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### 類型 (type)
- `feat`: 新功能
- `fix`: 修復問題
- `docs`: 文檔更新
- `style`: 代碼格式調整
- `refactor`: 代碼重構
- `test`: 測試相關
- `chore`: 維護性工作

### 示例
```bash
feat(agents): 添加卷級架構師代理
fix(expansion): 修復擴寫代理的上下文問題
docs(readme): 更新分卷式系統文檔
refactor(context): 重構上下文建構器架構
```

## Pull Request 規範

### PR 標題
- 清晰描述變更內容
- 使用與提交信息相同的格式

### PR 描述模板
```markdown
## 📋 變更摘要
<!-- 簡要描述這個 PR 做了什麼 -->

## 🎯 解決的問題
<!-- 這個 PR 解決了什麼問題或實現了什麼功能 -->

## 🧪 測試計劃
<!-- 如何測試這些變更 -->
- [ ] 單元測試通過
- [ ] 功能測試完成
- [ ] 集成測試驗證

## 📸 截圖（如適用）
<!-- 如果有 UI 變更，請提供截圖 -->

## ✅ 檢查清單
- [ ] 代碼已通過 linting
- [ ] 文檔已更新
- [ ] 測試已添加/更新
- [ ] CHANGELOG 已更新
```

## 當前狀態

- ✅ `main`: v3.0.0 分卷式系統基礎版本
- 🔧 `develop`: 當前開發分支，準備後續功能
- 📋 下一步：為新功能創建 feature 分支

## 後續開發建議

### 即將開發的功能分支
```bash
# API 配額管理優化
git checkout -b feature/api-quota-management

# 內容品質評估系統
git checkout -b feature/quality-assessment

# 角色對話代理
git checkout -b feature/dialogue-agent

# Web UI 界面
git checkout -b feature/web-interface
```