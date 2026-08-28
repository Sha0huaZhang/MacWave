#!/usr/bin/env ruby

require 'json'

# MacWave 仓库解析器
# 用法: ruby pkgparser.rb [pkginfo.txt]
# 输出: MacWave 兼容的 JSON 格式（包含 URL 模板、包信息、所有 releases）

class MacWaveParser
  def self.parse(content)
    # 去除所有注释
    clean = content.gsub(/<!--.*?-->/m, '')

    # 1. 提取 URL 模板（最重要的适配点！）
    url_templates = {}
    clean.scan(/let\s+"([^"]+)"\s*=\s*%f%\s+"([^"]+)"/) do |pkg, url|
      url_templates[pkg] = url
    end

    # 2. 解析包详情（%START% 到 %END%）
    packages = {}
    clean.scan(/"([^"]+)"\s*:\s*%START%\s*(.*?)\s*%END%/m) do |name, details|
      # 基础信息
      base = {
        'description' => '',
        'homepage' => '',
        'license' => '',
        'author' => '',
        'binary_name' => name,
        'releases' => []
      }

      versions = []
      sha256s = []
      bin_name = name

      # 解析键值对
      details.scan(/([a-z_]+)\s*:\s*(.*?)(?=\n\s*[a-z_]+\s*:|$)/m) do |key, raw_value|
        value = raw_value.strip.gsub(/\A"|"\z/, '')

        case key
        when 'des'
          base['description'] = value
        when 'hom'
          base['homepage'] = value
        when 'lic'
          base['license'] = value
        when 'aut'
          base['author'] = value
        when 'ver'
          # 多行版本处理
          if raw_value.include?("\n")
            versions = raw_value.split("\n").map { |v| v.strip.gsub(/\A"|"\z/, '') }.reject(&:empty?)
          else
            versions = [value]
          end
        when 'sha256'
          # 多行 SHA256 处理
          if raw_value.include?("\n")
            sha256s = raw_value.split("\n").map { |v| v.strip.gsub(/\A"|"\z/, '') }.reject(&:empty?)
          else
            sha256s = [value]
          end
        when 'bin_name'
          bin_name = value
        end
      end

      base['binary_name'] = bin_name
      base['homepage'] = base['homepage'] || ''

      # 3. 构建 releases（版本和 SHA256 严格按顺序一一对应）
      if versions.any?
        versions.each_with_index do |v, idx|
          base['releases'] << {
            'version' => v,
            'sha256' => sha256s[idx] || '',
            'arch' => 'any'
          }
        end
      else
        base['releases'] << {
          'version' => '0.0.0',
          'sha256' => sha256s.first || ''
        }
      end

      packages[name] = base
    end

    # 4. 把 URL 模板塞进包信息里（wave.py 的 _replace_version_placeholder 会用到它）
    packages.each do |name, info|
      if url_templates[name]
        info['binary_url'] = url_templates[name]
      end
    end

    { 'packages' => packages }
  end
end

# ============================================================
# 主程序
# ============================================================

def main
  file_path = ARGV[0] || 'pkginfo_arm64.txt'

  unless File.exist?(file_path)
    puts "Parser error, error code 001"
    exit 1
  end

  begin
    content = File.read(file_path, encoding: 'UTF-8')
  rescue => e
    puts "Parser error, error code 002"
    exit 1
  end

  result = MacWaveParser.parse(content)
  puts JSON.pretty_generate(result)
end

main if __FILE__ == $0
