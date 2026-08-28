#!/usr/bin/env ruby
# frozen_string_literal: true

# pkgparser.rb - MacWave 2.0 仓库解析器
# 用法: ruby pkgparser.rb [pkginfo.txt]
# 输出: 成功 -> JSON, 失败 -> Parser error, error code XXX
#
# ============================================================
# 错误码说明 / Error Code Reference
# ============================================================
# 001  - 文件未找到 / File not found
# 002  - 文件读取失败 / Failed to read file
# 003  - 语法错误 / Syntax error
# 004  - 版本号与 SHA256 数量不匹配 / Version count does not match SHA256 count
# 005  - 未知字段 / Unknown field
# 006  - 缩进错误 / Indentation error
# 099  - 其他未知错误 / Other unknown error
# ============================================================

require 'json'

# ============================================================
# 颜色定义
# ============================================================

RED_BOLD = "\033[1;31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# ============================================================
# 错误码 / Error Codes
# ============================================================

module ErrorCode
  FILE_NOT_FOUND = '001'
  FILE_READ_ERROR = '002'
  SYNTAX_ERROR = '003'
  VERSION_SHA256_MISMATCH = '004'
  UNKNOWN_FIELD = '005'
  INDENT_ERROR = '006'
  UNKNOWN_ERROR = '099'
end

# ============================================================
# 字段映射（简称 -> 全称）
# ============================================================

FIELD_MAP = {
  'des' => 'description',
  'hom' => 'homepage',
  'lic' => 'license',
  'aut' => 'author',
  'ver' => 'version',
  'sha256' => 'sha256',
  'bin_name' => 'binary_name',
  # 兼容全称
  'description' => 'description',
  'homepage' => 'homepage',
  'license' => 'license',
  'author' => 'author',
  'version' => 'version',
  'binary_name' => 'binary_name'
}.freeze

# ============================================================
# 解析器
# ============================================================

class RepoParser
  INDENT_SIZE = 4

  attr_reader :packages, :errors

  def initialize
    @packages = {}
    @errors = []
    @line_num = 0
    @content = []
    @current_package = nil
    @in_start_block = false
    @current_fields = {}
    @current_versions = []
    @current_sha256s = []
    @current_multiline_key = nil
    @current_multiline_values = []
    @parse_download_version = nil
  end

  def parse(content)
    @content = content.each_line.map(&:chomp)
    i = 0

    # 第一遍扫描：提取 parse_download_version 和 URL 模板
    @content.each do |line|
      if line.include?('parse_download_version')
        match = line.match(/let\s+"parse_download_version"\s*=\s*\{([^}]+)\}/)
        @parse_download_version = match[1] if match
      end
    end

    while i < @content.length
      @line_num = i + 1
      line = @content[i]
      stripped = line.strip

      # 跳过空行
      if stripped.empty?
        i += 1
        next
      end

      # 跳过注释
      if stripped.start_with?('<!--')
        if stripped.include?('-->')
          i += 1
          next
        end
        while i < @content.length && !@content[i].include?('-->')
          i += 1
        end
        i += 1
        next
      end

      # 跳过 $ ... $ 区块标记
      if stripped.start_with?('$') && stripped.end_with?('$')
        i += 1
        next
      end

      # 跳过 def repo_dict:, {repo_url:, let, [package_info:, }, ]
      if stripped == 'def repo_dict:' || stripped == '{repo_url:' || stripped == '}' || stripped == 'let' || stripped == '[package_info:' || stripped == ']'
        i += 1
        next
      end

      # 跳过 let 定义行（只要以 let 开头的都跳过）
      if stripped.start_with?('let ')
        i += 1
        next
      end

      # ============================================================
      # 解析包名: "ldid":
      # ============================================================
      if stripped.match?(/^"[^"]+":\s*$/)
        @current_package = stripped.tr('":', '')
        @packages[@current_package] = {
          'description' => '',
          'homepage' => '',
          'license' => '',
          'author' => '',
          'binary_name' => '',
          'releases' => []
        }
        @current_fields = {}
        @current_versions = []
        @current_sha256s = []
        i += 1
        next
      end

      # ============================================================
      # 解析 %START%
      # ============================================================
      if stripped == '%START%'
        @in_start_block = true
        @current_fields = {}
        @current_versions = []
        @current_sha256s = []
        @current_multiline_key = nil
        @current_multiline_values = []
        i += 1
        next
      end

      # ============================================================
      # 解析 %END%
      # ============================================================
      if stripped == '%END%'
        @in_start_block = false

        unless @current_package.nil?
          # 处理可能剩余的多行值
          if @current_multiline_key && @current_multiline_values.any?
            if @current_multiline_key == 'ver'
              @current_versions.concat(@current_multiline_values)
            elsif @current_multiline_key == 'sha256'
              @current_sha256s.concat(@current_multiline_values)
            end
            @current_multiline_key = nil
            @current_multiline_values = []
          end

          # 检查是否有多版本数据
          if @current_versions.any?
            # 多版本模式：ver 和 sha256 按顺序配对
            if @current_versions.length == @current_sha256s.length
              @current_versions.each_with_index do |ver, idx|
                sha = @current_sha256s[idx] || ''
                release = {
                  'version' => ver,
                  'sha256' => sha
                }
                @packages[@current_package]['releases'] << release
              end
            else
              error(ErrorCode::VERSION_SHA256_MISMATCH,
                    "version count (#{@current_versions.length}) != sha256 count (#{@current_sha256s.length})")
              return false
            end
          elsif @current_fields.key?('version')
            release = {
              'version' => @current_fields['version'],
              'sha256' => @current_fields['sha256'] || ''
            }
            @packages[@current_package]['releases'] << release
          end

          # 保存共享字段
          %w[description homepage license author binary_name].each do |field|
            if @current_fields.key?(field)
              @packages[@current_package][field] = @current_fields[field]
            end
          end

          begin
            @packages[@current_package]['releases'].sort! do |a, b|
              compare_versions(b['version'], a['version'])
            end
          rescue
          end
        end

        i += 1
        next
      end

      # ============================================================
      # 解析带引号的多行值（例如 "2.1.5-procursus7"）
      # ============================================================
      if @current_multiline_key && stripped.start_with?('"') && stripped.end_with?('"')
        value = stripped[1..-2]  # 去除首尾双引号
        @current_multiline_values << value
        i += 1
        next
      end

      # ============================================================
      # 解析字段: key: "value"
      # ============================================================
      if @in_start_block && stripped.include?(':')
        # 先结算之前的多行值
        if @current_multiline_key && @current_multiline_values.any?
          if @current_multiline_key == 'ver'
            @current_versions.concat(@current_multiline_values)
          elsif @current_multiline_key == 'sha256'
            @current_sha256s.concat(@current_multiline_values)
          end
          @current_multiline_key = nil
          @current_multiline_values = []
        end

        key, value = stripped.split(':', 2)
        key = key.strip
        value = value.strip

        # 检查缩进
        indent = line.length - line.lstrip.length
        unless indent % INDENT_SIZE == 0
          error(ErrorCode::INDENT_ERROR,
                "indentation must be multiple of #{INDENT_SIZE}, got #{indent}")
          return false
        end

        # 处理多行值（如果 value 为空或只有引号，可能是多行）
        if value.empty? || value == '""' || value == '"'
          @current_multiline_key = key
          @current_multiline_values = []
          i += 1
          next
        end

        # 去引号
        if value.start_with?('"') && value.end_with?('"')
          value = value[1..-2]
        end

        # 映射字段名
        normalized_key = FIELD_MAP[key] || key

        # 检查是否为未知字段
        unless FIELD_MAP.value?(normalized_key) || normalized_key == 'sha256'
          error(ErrorCode::UNKNOWN_FIELD, "unknown field: '#{key}'")
          return false
        end

        # 特殊处理 ver 和 sha256（累加）
        if normalized_key == 'version'
          @current_versions << value
        elsif normalized_key == 'sha256'
          @current_sha256s << value
        else
          @current_fields[normalized_key] = value
        end

        i += 1
        next
      end

      # 如果不在多行模式下，遇到其他行直接跳过
      i += 1
    end

    # 处理最后一个未闭合的块
    if @current_multiline_key && @current_multiline_values.any?
      if @current_multiline_key == 'ver'
        @current_versions.concat(@current_multiline_values)
      elsif @current_multiline_key == 'sha256'
        @current_sha256s.concat(@current_multiline_values)
      end
    end

    @errors.empty?
  end

  private

  def compare_versions(v1, v2)
    parts1 = v1.to_s.split('.').map { |p| p.match?(/^\d+$/) ? p.to_i : p }
    parts2 = v2.to_s.split('.').map { |p| p.match?(/^\d+$/) ? p.to_i : p }

    max_len = [parts1.length, parts2.length].max
    max_len.times do |i|
      a = parts1[i]
      b = parts2[i]
      return -1 if a.nil?
      return 1 if b.nil?

      if a.is_a?(Integer) && b.is_a?(Integer)
        return -1 if a < b
        return 1 if a > b
      else
        return -1 if a.to_s < b.to_s
        return 1 if a.to_s > b.to_s
      end
    end
    0
  end

  def error(code, message)
    @errors << { code: code, message: message, line: @line_num }
  end
end

# ============================================================
# 主程序
# ============================================================

def main
  file_path = ARGV[0] || 'pkginfo_arm64.txt'

  unless File.exist?(file_path)
    puts "#{RED_BOLD}Parser error, error code #{ErrorCode::FILE_NOT_FOUND}#{RESET}"
    exit 1
  end

  begin
    content = File.read(file_path, encoding: 'UTF-8')
  rescue => e
    puts "#{RED_BOLD}Parser error, error code #{ErrorCode::FILE_READ_ERROR}#{RESET}"
    exit 1
  end

  parser = RepoParser.new
  success = parser.parse(content)

  unless success
    if parser.errors.any?
      puts "#{RED_BOLD}Parser error, error code #{parser.errors.first[:code]}#{RESET}"
    else
      puts "#{RED_BOLD}Parser error, error code #{ErrorCode::UNKNOWN_ERROR}#{RESET}"
    end
    exit 1
  end

  puts JSON.pretty_generate(parser.packages)
end

main if __FILE__ == $0
