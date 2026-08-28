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
  # 001: 文件未找到
  FILE_NOT_FOUND = '001'
  # 002: 文件读取失败
  FILE_READ_ERROR = '002'
  # 003: 语法错误
  SYNTAX_ERROR = '003'
  # 004: 版本号与 SHA256 数量不匹配
  VERSION_SHA256_MISMATCH = '004'
  # 005: 未知字段
  UNKNOWN_FIELD = '005'
  # 006: 缩进错误
  INDENT_ERROR = '006'
  # 099: 其他未知错误
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
  'bin_name' => 'binary_name'
}.freeze

# ============================================================
# 解析器
# ============================================================

class RepoParser
  attr_reader :packages, :errors

  def initialize
    @packages = {}
    @errors = []
    @line_num = 0
    @content = []
    @current_package = nil
    @current_fields = {}
    @current_versions = []
    @current_sha256s = []
    @current_ver_sha_pairs = []
    @current_list_key = nil
    @current_list_values = []
    @state = :initial
    @in_start_block = false
  end

  def parse(content)
    @content = content.each_line.map(&:chomp)
    i = 0

    while i < @content.length
      @line_num = i + 1
      line = @content[i]
      stripped = line.strip

      # ---------- 跳过空行 ----------
      if stripped.empty?
        i += 1
        next
      end

      # ---------- 跳过注释 ----------
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

      # ---------- 处理 $ ... $ 区块标记（改变解析状态） ----------
      if stripped.start_with?('$') && stripped.end_with?('$')
        stripped = stripped.gsub(/^\$\s*|\s*\$/, '').strip
        stripped = stripped.gsub(/^\\/, '').strip
        case stripped
        when 'PackagesDictionary'
          @state = :dictionary
        when 'PackagesURL'
          @state = :urls
        when 'PackagesDetails'
          @state = :details
        else
          @state = :initial
        end
        i += 1
        next
      end

      # ---------- 在 URL 区：处理 let 模板 ----------
      if @state == :urls && stripped.start_with?('let ')
        @current_let_key = stripped.split('=')[0].strip.gsub(/^let\s+/, '').gsub(/"/, '')
        i += 1
        next
      end

      # ---------- 在详情区：处理包名 ----------
      if @state == :details && stripped.match?(/^"[^"]+":\s*$/)
        finalize_package

        @current_package = stripped.split(':')[0].gsub(/"/, '').strip
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
        @current_ver_sha_pairs = []
        @current_list_key = nil
        @current_list_values = []
        i += 1
        next
      end

      # ---------- 处理 %START% 和 %END% ----------
      if stripped == '%START%'
        @in_start_block = true
        @current_fields = {}
        @current_versions = []
        @current_sha256s = []
        @current_ver_sha_pairs = []
        @current_list_key = nil
        @current_list_values = []
        i += 1
        next
      end

      if stripped == '%END%'
        @in_start_block = false
        finalize_package
        i += 1
        next
      end

      # ---------- 在详情区且处于 %START% 和 %END% 之间 ----------
      if @state == :details && @in_start_block
        # 收集多行列表的后续值（被引号包裹的缩进行）
        if @current_list_key && stripped.start_with?('"') && stripped.end_with?('"')
          value = stripped.gsub(/\A"|"\z/, '')
          @current_list_values << value
          i += 1
          next
        end

        if stripped.include?(':')
          indent = line.length - line.lstrip.length
          unless indent % 4 == 0
            error(ErrorCode::INDENT_ERROR, "indentation must be multiple of 4, got #{indent}")
            return false
          end

          # 结算上一个多行列表
          if @current_list_key
            if @current_list_key == 'version'
              @current_versions.concat(@current_list_values)
            elsif @current_list_key == 'sha256'
              @current_sha256s.concat(@current_list_values)
            end
            @current_list_key = nil
            @current_list_values = []
          end

          key, value = stripped.split(':', 2)
          key = key.strip
          value = value.strip
          value = value.gsub(/\A"|"\z/, '')

          unless FIELD_MAP.key?(key)
            error(ErrorCode::UNKNOWN_FIELD, "unknown field: '#{key}'")
            return false
          end

          normalized_key = FIELD_MAP[key]

          if normalized_key == 'version' || normalized_key == 'sha256'
            @current_list_key = normalized_key
            @current_list_values = [value]
          else
            @current_fields[normalized_key] = value
          end

          i += 1
          next
        end
      end

      # ---------- 其他情况全部跳过 ----------
      i += 1
    end

    # 文件末尾收尾
    finalize_package

    @errors.empty?
  end

  private

  def finalize_package
    return unless @current_package

    # 结算最后可能未处理的列表
    if @current_list_key
      if @current_list_key == 'version'
        @current_versions.concat(@current_list_values)
      elsif @current_list_key == 'sha256'
        @current_sha256s.concat(@current_list_values)
      end
      @current_list_key = nil
      @current_list_values = []
    end

    # 检查数量是否匹配
    if @current_versions.any? || @current_sha256s.any?
      unless @current_versions.length == @current_sha256s.length
        error(ErrorCode::VERSION_SHA256_MISMATCH,
              "version count (#{@current_versions.length}) != sha256 count (#{@current_sha256s.length})")
        return false
      end

      @current_versions.each_with_index do |ver, idx|
        sha = @current_sha256s[idx] || ''
        @packages[@current_package]['releases'] << {
          'version' => ver,
          'sha256' => sha
        }
      end
    end

    # 保存共享字段
    %w[description homepage license author binary_name].each do |field|
      if @current_fields.key?(field)
        @packages[@current_package][field] = @current_fields[field]
      end
    end

    # 按版本排序
    begin
      @packages[@current_package]['releases'].sort! do |a, b|
        compare_versions(b['version'], a['version'])
      end
    rescue
      # 保持原顺序
    end
  end

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
