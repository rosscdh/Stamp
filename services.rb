require 'pdfkit'

module Stamp
    class HTML2PDFService
        def initialize(html, filename=nil, css=nil, page_size='Legal')
            @html = html
            @page_size = page_size
            @css = css
            @filename = filename

            @service = PDFKit.new(@html, :page_size => @page_size)
            @service.stylesheets << @css if not @css.nil?
        end

        def as_file
            @service.to_file(@filename)
        end

        def as_inline_pdf
            @service.to_pdf
        end
    end
end