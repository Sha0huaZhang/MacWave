#!/usr/bin/env ruby

require 'json'

class MacWaveParser
  def self.parse(content)
    # 去掉所有注释
    clean = content.gsub(/<!--.*?-->/m, '')

    # 1. 提取 URL 模板
    url_templates = {}
    clean.scan(/let\s+"([^"]+)"\s*=\s*%f%\s+"([^"]+)"/) do |pkg, url|
      url_templates[pkg] = url
    end

    # 2. 逐行状态机解析包
    packages = []
    current_package = nil
    current_fields = {}
    current_versions = []
    current_sha256s = []
    in_start_block = false
    in_ver_list = false
    in_sha256_list = false

    clean.each_line do |line|
      stripped = line.strip

      # 遇到新的包名
      if stripped.match?(/^"[^"]+":\s*$/)
        # 结算上一个包
        if current_package
          releases = []
          if current_versions.any?
            current_versions.each_with_index do |v, idx|
              releases << {
                'version' => v,
                'sha256' => current_sha256s[idx] || '',
                'arch' => 'any'
              }
            end
          else
            releases << {
              'version' => '0.0.0',
              'sha256' => current_sha256s.first || ''
            }
          end

          packages << {
            'name' => current_package,
            'version' => current_versions.first || '0.0.0',
            'description' => current_fields['description'] || '',
            'homepage' => current_fields['homepage'] || '',
            'license' => current_fields['license'] || '',
            'author' => current_fields['author'] || '',
            'binary_name' => current_fields['binary_name'] || current_package,
            'releases' => releases
          }
        end

        current_package = stripped.gsub(/"/, '').chomp(':')
        current_fields = {}
        current_versions = []
        current_sha256s = []
        in_ver_list = false
        in_sha256_list = false
        next
      end

      # 解析 %START%
      if stripped == '%START%'
        in_start_block = true
        current_fields = {}
        current_versions = []
        current_sha256s = []
        in_ver_list = false
        in_sha256_list = false
        next
      end

      # 解析 %END%
      if stripped == '%END%'
        in_start_block = false
        next
      end

      # 必须在 %START% 和 %END% 之间
      next unless in_start_block

      # 处理多行版本列表
      if in_ver_list && stripped.start_with?('"') && stripped.end_with?('"')
        value = stripped.gsub(/\A"|"\z/, '')
        current_versions << value
        next
      end

      # 处理多行 SHA256 列表
      if in_sha256_list && stripped.start_with?('"') && stripped.end_with?('"')
        value = stripped.gsub(/\A"|"\z/, '')
        current_sha256s << value
        next
      end

      # 解析 key: value
      if stripped.include?(':')
        key, value = stripped.split(':', 2)
        key = key.strip
        value = value.strip.gsub(/\A"|"\z/, '')

        case key
        when 'des'
          current_fields['description'] = value
        when 'hom'
          current_fields['homepage'] = value
        when 'lic'
          current_fields['license'] = value
        when 'aut'
          current_fields['author'] = value
        when 'ver'
          current_versions = [value]
          in_ver_list = true
          in_sha256_list = false
        when 'sha256'
          current_sha256s = [value]
          in_sha256_list = true
          in_ver_list = false
        when 'bin_name'
          current_fields['binary_name'] = value
        end
      end
    end

    # 结算最后一个包
    if current_package
      releases = []
      if current_versions.any?
        current_versions.each_with_index do |v, idx|
          releases << {
            'version' => v,
            'sha256' => current_sha256s[idx] || '',
            'arch' => 'any'
          }
        end
      else
        releases << {
          'version' => '0.0.0',
          'sha256' => current_sha256s.first || ''
        }
      end

      packages << {
        'name' => current_package,
        'version' => current_versions.first || '0.0.0',
        'description' => current_fields['description'] || '',
        'homepage' => current_fields['homepage'] || '',
        'license' => current_fields['license'] || '',
        'author' => current_fields['author'] || '',
        'binary_name' => current_fields['binary_name'] || current_package,
        'releases' => releases
      }
    end

    # 3. 把 URL 模板塞进包信息
    packages.each do |pkg|
      if url_templates[pkg['name']]
        pkg['binary_url'] = url_templates[pkg['name']]
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
