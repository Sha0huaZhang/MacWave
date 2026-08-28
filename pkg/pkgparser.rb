#!/usr/bin/env ruby
# frozen_string_literal: true

# parser.rb - MacWave 2.0 仓库解析器
# 用法: ruby parser.rb [pkginfo.txt]
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
  FILE_NOT_FOUND = '001'          # 文件未找到 / File not found
  FILE_READ_ERROR = '002'         # 文件读取失败 / Failed to read file
  SYNTAX_ERROR = '003'            # 语法错误 / Syntax error
  VERSION_SHA256_MISMATCH = '004' # 版本号与 SHA256 数量不匹配 / Version count does not match SHA256 count
  UNKNOWN_FIELD = '005'           # 未知字段 / Unknown field
  INDENT_ERROR = '006'            # 缩进错误 / Indentation error
  UNKNOWN_ERROR = '099'           # 其他未知错误 / Other unknown error
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
  'bin_name' => 'binary_name'
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
    @expecting_multiline = false
    @current_key = nil
    @multiline_values = []
    @parse_download_version = nil
  end

  def parse(content)
    @content = content.each_line.map(&:chomp)
    i = 0

    # 第一遍扫描：提取 parse_download_version
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

      # 跳过注释 <!-- ... -->
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

      # 跳过 def repo_dict: 区块
      if stripped == 'def repo_dict:'
        i += 1
        next
      end

      # 跳过 {repo_url: 区块（但提取 URL 变量）
      if stripped == '{repo_url:'
        i += 1
        next
      end

      if stripped == '}'
        i += 1
        next
      end

      # 跳过 let 定义（但提取 URL 模板）
      if stripped.start_with?('let ')
        i += 1
        next
      end

      # 跳过 [package_info:
      if stripped == '[package_info:'
        i += 1
        next
      end

      if stripped == ']'
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
        @expecting_multiline = false
        @multiline_values = []
        @current_key = nil
        i += 1
        next
      end

      # ============================================================
      # 解析 %END%
      # ============================================================
      if stripped == '%END%'
        @in_start_block = false

        # 处理当前收集的数据
        unless @current_package.nil?
          # 如果有缩进的多行值，处理它们
          if @expecting_multiline && @multiline_values.any?
            process_multiline_values
          end

          # 检查是否有多版本数据
          if @current_versions.any?
            # 多版本模式：ver 和 sha256 按顺序配对
            if @current_versions.length == @current_sha256s.length
              @current_versions.each_with_index do |ver, idx|
                sha = @current_sha256s[idx] || ''
                # 版本排序：越新越靠前
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
            # 单版本模式：从字段中取
            release = {
              'version' => @current_fields['version'],
              'sha256' => @current_fields['sha256'] || ''
            }
            @packages[@current_package]['releases'] << release
          end

          # 保存共享字段（所有版本共享）
          %w[description homepage license author binary_name].each do |field|
            if @current_fields.key?(field)
              @packages[@current_package][field] = @current_fields[field]
            end
          end

          # 按版本从新到旧排序
          begin
            @packages[@current_package]['releases'].sort! do |a, b|
              compare_versions(b['version'], a['version'])
            end
          rescue
            # 如果版本比较失败，保持原顺序
          end
        end

        i += 1
        next
      end

      # ============================================================
      # 解析字段: key: "value"
      # ============================================================
      if @in_start_block && stripped.include?(':') && !stripped.start_with?('<!--')
        # 检查缩进
        indent = line.length - line.lstrip.length
        unless indent % INDENT_SIZE == 0
          error(ErrorCode::INDENT_ERROR,
                "indentation must be multiple of #{INDENT_SIZE}, got #{indent}")
          return false
        end

        key, value = stripped.split(':', 2)
        key = key.strip
        value = value.strip

        # 处理多行值（如果 value 为空或只有引号，可能是多行）
        if value.empty? || value == '""' || value == '"'
          @expecting_multiline = true
          @current_key = key
          @multiline_values = []
          i += 1
          next
        end

        # 移除 value 两端的引号
        value = value.tr('"', '')

        # 映射字段名
        normalized_key = FIELD_MAP[key] || key

        # 检查是否为未知字段（不在映射表中）
        unless FIELD_MAP.key?(key) || key == 'sha256'
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

      # ============================================================
      # 解析多行值（缩进的行）
      # ============================================================
      if @expecting_multiline && stripped.start_with?('"')
        value = stripped.tr('"', '')
        @multiline_values << value
        i += 1
        next
      end

      # 多行值结束（遇到非缩进行或空行）
      if @expecting_multiline && !stripped.start_with?('"') && !stripped.empty?
        process_multiline_values
        @expecting_multiline = false
        # 不增加 i，重新处理当前行
        next
      end

      i += 1
    end

    # 处理最后一个未闭合的块
    if @expecting_multiline && @multiline_values.any?
      process_multiline_values
    end

    @errors.empty?
  end

  private

  def process_multiline_values
    return unless @current_key

    normalized_key = FIELD_MAP[@current_key] || @current_key

    if normalized_key == 'version'
      @current_versions.concat(@multiline_values)
    elsif normalized_key == 'sha256'
      @current_sha256s.concat(@multiline_values)
    else
      @current_fields[normalized_key] = @multiline_values.join(' ')
    end

    @multiline_values = []
    @current_key = nil
  end

  def compare_versions(v1, v2)
    # 简单版本比较：按点分割，逐段比较
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
    # 输出第一个错误的错误码
    if parser.errors.any?
      puts "#{RED_BOLD}Parser error, error code #{parser.errors.first[:code]}#{RESET}"
    else
      puts "#{RED_BOLD}Parser error, error code #{ErrorCode::UNKNOWN_ERROR}#{RESET}"
    end
    exit 1
  end

  # 输出 JSON
  puts JSON.pretty_generate(parser.packages)
end

main if __FILE__ == $0
