#!/usr/bin/env ruby
# frozen_string_literal: true

# waveparser.rb - MacWave 2.0 仓库解析器
# 用法: ruby waveparser.rb [repoindex.txt]
# 输出: 包含所有包信息的 JSON 格式数据

require 'json'
require 'pathname'

# ==================== 数据结构定义 ====================

class ExcludeRule
  attr_reader :pattern, :unless_list
  def initialize(pattern, unless_list = [])
    @pattern = pattern
    @unless_list = unless_list
  end
end

class PackageBlock
  attr_accessor :name, :version, :arch, :sha256, :binary_url, :filename, :homepage, :license
  def initialize(name)
    @name = name
    @version = nil
    @arch = nil
    @sha256 = nil
    @binary_url = nil
    @filename = nil
    @homepage = nil
    @license = nil
  end
end

# ==================== 解析器 ====================

class RepoParser
  attr_reader :packages, :variables, :errors

  INDENT_SIZE = 4

  def initialize
    @packages = {}       # 存储解析出的包信息
    @variables = {}      # 存储 let 定义的 URL 变量
    @errors = []         # 错误列表
    @line_num = 0        # 当前行号
    @current_block = nil # 当前正在解析的包块
    @in_repo_dict = false
    @in_repo_url = false
    @in_package_info = false
  end

  def parse(content)
    lines = content.each_line.map(&:chomp)
    i = 0

    while i < lines.length
      @line_num = i + 1
      line = lines[i]
      stripped = line.strip

      # 跳过空行
      if stripped.empty?
        i += 1
        next
      end

      # 跳过注释（<!-- ... -->）
      if stripped.start_with?('<!--')
        if stripped.include?('-->')
          i += 1
          next
        end
        while i < lines.length && !lines[i].include?('-->')
          i += 1
        end
        i += 1
        next
      end

      # 解析 def repo_dict: 开始
      if stripped.start_with?('def repo_dict:')
        @in_repo_dict = true
        i += 1
        next
      end

      # 解析 {repo_url: 开始
      if stripped.start_with?('{repo_url:')
        @in_repo_url = true
        i += 1
        next
      end

      # 解析 } 结束 repo_url 块
      if stripped == '}' && @in_repo_url
        @in_repo_url = false
        i += 1
        next
      end

      # 解析 [package_info: 开始
      if stripped.start_with?('[package_info:')
        @in_package_info = true
        i += 1
        next
      end

      # 解析 ] 结束 package_info 块
      if stripped == ']' && @in_package_info
        @in_package_info = false
        i += 1
        next
      end

      # 解析 repo_dict 中的包名
      if @in_repo_dict && stripped.start_with?('"') && stripped.end_with?('"')
        package_name = stripped.tr('"', '')
        # 暂时不处理，只做验证
        i += 1
        next
      end

      # 解析 repo_url 中的 let 定义
      if @in_repo_url && stripped.start_with?('let ')
        match = stripped.match(/let\s+"([^"]+)"\s*=\s*"([^"]+)"/)
        if match
          name, url = match.captures
          if @variables.key?(name)
            @errors << "Line #{@line_num}: variable '#{name}' already defined"
          else
            @variables[name] = url
          end
        else
          @errors << "Line #{@line_num}: invalid 'let' syntax"
        end
        i += 1
        next
      end

      # 解析 package_info 中的包声明
      if @in_package_info && stripped.start_with?('"') && stripped.end_with?(':')
        package_name = stripped.chomp(':').tr('"', '')
        @current_block = PackageBlock.new(package_name)
        i += 1
        next
      end

      # 解析 package_info 中的属性
      if @in_package_info && @current_block && stripped.include?(':')
        # 检查缩进
        indent = line.length - line.lstrip.length
        unless indent % INDENT_SIZE == 0
          @errors << "Line #{@line_num}: indentation must be multiple of #{INDENT_SIZE}, got #{indent}"
        end

        if stripped.start_with?('version:')
          @current_block.version = stripped.sub('version:', '').strip.tr('"', '')
        elsif stripped.start_with?('arch:')
          @current_block.arch = stripped.sub('arch:', '').strip.tr('"', '')
        elsif stripped.start_with?('sha256:')
          @current_block.sha256 = stripped.sub('sha256:', '').strip.tr('"', '')
        elsif stripped.start_with?('binary_url:')
          url_str = stripped.sub('binary_url:', '').strip.tr('"', '')
          # 处理变量引用：$变量名 -> 实际 URL
          if url_str.start_with?('$')
            var_name = url_str[1..-1]
            if @variables.key?(var_name)
              @current_block.binary_url = @variables[var_name]
            else
              @errors << "Line #{@line_num}: undefined variable '$#{var_name}'"
            end
          else
            @current_block.binary_url = url_str
          end
        elsif stripped.start_with?('filename:')
          @current_block.filename = stripped.sub('filename:', '').strip.tr('"', '')
        elsif stripped.start_with?('homepage:')
          @current_block.homepage = stripped.sub('homepage:', '').strip.tr('"', '')
        elsif stripped.start_with?('license:')
          @current_block.license = stripped.sub('license:', '').strip.tr('"', '')
        else
          @errors << "Line #{@line_num}: unknown attribute '#{stripped}'"
        end
        i += 1
        next
      end

      # 遇到空行或非缩进行表示当前包结束
      if @in_package_info && @current_block && !stripped.start_with?('"')
        @packages[@current_block.name] = {
          "version" => @current_block.version,
          "arch" => @current_block.arch,
          "sha256" => @current_block.sha256,
          "binary_url" => @current_block.binary_url,
          "filename" => @current_block.filename,
          "homepage" => @current_block.homepage,
          "license" => @current_block.license
        }
        @current_block = nil
        # 不增加 i，继续处理当前行
      end

      i += 1
    end

    # 处理最后一个未闭合的包
    if @current_block
      @packages[@current_block.name] = {
        "version" => @current_block.version,
        "arch" => @current_block.arch,
        "sha256" => @current_block.sha256,
        "binary_url" => @current_block.binary_url,
        "filename" => @current_block.filename,
        "homepage" => @current_block.homepage,
        "license" => @current_block.license
      }
    end

    @errors.empty?
  end
end

# ==================== 主程序 ====================

def main
  file_path = ARGV[0] || 'repoindex.txt'
  
  unless File.exist?(file_path)
    $stderr.puts "Error: File '#{file_path}' not found."
    exit 1
  end

  begin
    content = File.read(file_path)
  rescue => e
    $stderr.puts "Error reading file: #{e.message}"
    exit 1
  end

  parser = RepoParser.new
  success = parser.parse(content)

  unless success
    parser.errors.each { |err| $stderr.puts "Error: #{err}" }
    exit 1
  end

  # 输出 JSON 格式，供 wave.py 调用
  puts JSON.pretty_generate(parser.packages)
end

main if __FILE__ == $0
