# 跨机器记忆同步

本目录包含 Claude Code 的持久化记忆文件，用于在不同机器之间共享项目上下文。

## 在新机器上恢复记忆

```bash
# 1. Clone 项目
git clone https://github.com/Vincentxiaojie/Klipper-xPainter.git
cd Klipper-xPainter

# 2. 确定 Claude Code 的记忆路径
PROJECT_PATH=$(pwd)
MEMORY_PATH="$HOME/.claude/projects/$PROJECT_PATH"

# 3. 方式 A：软链接（推荐，git pull 后自动同步）
mkdir -p "$MEMORY_PATH"
ln -s "$PROJECT_PATH/memory"/*.md "$MEMORY_PATH/"
# 注意：MEMORY.md 必须覆盖
cp "$PROJECT_PATH/memory/MEMORY.md" "$MEMORY_PATH/MEMORY.md"

# 4. 方式 B：复制（手动同步）
mkdir -p "$MEMORY_PATH"
cp "$PROJECT_PATH/memory/"*.md "$MEMORY_PATH/"

# 5. 验证
ls "$MEMORY_PATH"
```

## 更新记忆

在任何一台机器上更新记忆后：

```bash
cp ~/.claude/projects/$(pwd)/memory/*.md memory/
git add memory/
git commit -m "docs: 更新跨机器记忆"
git push
```

在其他机器上拉取：

```bash
git pull
cp memory/*.md ~/.claude/projects/$(pwd)/memory/
```

## 记忆类型

| 文件 | 类型 | 说明 |
|------|------|------|
| `MEMORY.md` | 索引 | 所有记忆的索引（Claude Code 自动加载） |
| `x-five-axis-progress.md` | project | 五轴扩展完整进度、设计决策、待解决问题 |
| `gcode-macro-override.md` | feedback | gcode.py register_command 覆盖模式 |
| `test-coverage-gap.md` | project | 测试盲区与预存失败清单 |
| `g43-tool-length.md` | project | G43 工具长度配置待实现 |
| `klipper-motion-algo-test.md` | project | 运动算法测试 |
| `project-goal.md` | project | 项目目标概述 |
