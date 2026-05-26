#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将本地多层级文档转换为 GitHub Wiki 兼容的拍平结构，并修正链接。
1. 清理或创建输出文件夹。
2. 递归读取 docs/ 目录下的所有 .md 文件，将它们拷贝到输出文件夹。
3. 子目录下的文件重命名为 '目录名-文件名.md'（例如 docs/adr/xxx.md -> adr-xxx.md）。
4. 转换 docs/README.md 为 Home.md 和 _Sidebar.md。
5. 读取每个转换后的文件，通过正则匹配，自动修正相对链接（如 [Label](../current-status.md) -> [Label](current-status)）。
"""

import os
import re
import sys
import shutil

def normalize_relative_path(path):
    # 去除路径中的 '.' 和 '..'
    normalized = os.path.normpath(path).replace('\\', '/')
    return normalized

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    docs_dir = os.path.join(repo_root, "docs")
    
    # 默认输出路径为 repo_root/out-wiki
    output_dir = os.path.join(repo_root, "out-wiki")
    if len(sys.argv) > 1:
        output_dir = os.path.abspath(sys.argv[1])
        
    print(f"Docs directory: {docs_dir}")
    print(f"Output directory: {output_dir}")
    
    # 1. 准备输出目录
    if os.path.exists(output_dir):
        print("Cleaning existing output directory...")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. 收集 docs/ 目录下的所有文件并建立映射
    # 键：相对于 docs/ 的相对路径，值：Wiki 中的页面名称（不含 .md）
    path_map = {}
    files_to_process = []
    
    for root, _, files in os.walk(docs_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            full_path = os.path.join(root, file)
            # 计算相对于 docs/ 的相对路径
            rel_path = os.path.relpath(full_path, docs_dir).replace('\\', '/')
            
            # 确定 Wiki 页面文件名
            if rel_path == "README.md":
                wiki_name = "Home"
            else:
                base = rel_path[:-3]  # 去掉 .md 后缀
                wiki_name = base.replace('/', '-')
                
            path_map[rel_path] = wiki_name
            files_to_process.append({
                "full_path": full_path,
                "rel_path": rel_path,
                "wiki_name": wiki_name
            })
            
    # 3. 拷贝并转换文件
    for item in files_to_process:
        dest_path = os.path.join(output_dir, f"{item['wiki_name']}.md")
        print(f"Processing: {item['rel_path']} -> {item['wiki_name']}.md")
        
        # 读取原始内容
        with open(item['full_path'], 'r', encoding='utf-8') as f:
            content = f.read()
            
        current_rel_dir = os.path.dirname(item['rel_path']).replace('\\', '/')
        if current_rel_dir == "":
            current_rel_dir = "."
            
        # 4. 正则匹配并替换 Markdown 中的相对链接
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        
        def replace_link(match):
            label = match.group(1)
            link = match.group(2)
            
            # 跳过绝对链接、邮件链接或纯锚点链接
            if re.match(r'^(https?://|mailto:|#)', link):
                return match.group(0)
                
            # 提取锚点（如果有）
            anchor = ""
            anchor_match = re.search(r'#(.+)$', link)
            if anchor_match:
                anchor = "#" + anchor_match.group(1)
                link_without_anchor = re.sub(r'#(.+)$', '', link)
            else:
                link_without_anchor = link
                
            # 仅处理指向 .md 文件的链接
            if link_without_anchor.endswith(".md"):
                # 组合当前文件目录与被引用的相对链接
                combined = f"{current_rel_dir}/{link_without_anchor}"
                target_rel = normalize_relative_path(combined)
                
                if target_rel in path_map:
                    target_wiki_name = path_map[target_rel]
                    return f"[{label}]({target_wiki_name}{anchor})"
                else:
                    # 不在 docs/ 目录下，寻找相对于项目根目录的路径
                    from_root_path = f"docs/{current_rel_dir}/{link_without_anchor}"
                    root_rel = normalize_relative_path(from_root_path)
                    
                    # 验证该文件是否确实在项目根目录下存在
                    full_target = os.path.join(repo_root, root_rel)
                    if os.path.exists(full_target):
                        # 替换为 GitHub 绝对链接
                        github_url = f"https://github.com/tylevnovik/TextFlow/blob/main/{root_rel}{anchor}"
                        return f"[{label}]({github_url})"
                        
            return match.group(0)
            
        new_content = re.sub(pattern, replace_link, content)
        
        # 写入新文件
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        # 特别处理：如果当前是 README.md，除了生成 Home.md，还需要复制一份作为 _Sidebar.md 侧边栏
        if item['rel_path'] == "README.md":
            sidebar_path = os.path.join(output_dir, "_Sidebar.md")
            print("Creating _Sidebar.md from README.md")
            with open(sidebar_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
    print(f"Docs conversion completed. Artifacts are at: {output_dir}")

if __name__ == "__main__":
    main()
