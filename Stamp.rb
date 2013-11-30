require 'grape'
require 'pdfkit'

module Stamp
  class API < Grape::API

    version 'v1', using: :path

    resource :html do

      desc "Post HTML get PDF in response"
      params do
        requires :html, type: String, desc: "Raw HTML"
        requires :filename, type: String, desc: "Name of file to generate"
      end
      post "/to/pdf" do
        html = params[:html]
        filename = params[:filename]
        file_path = '/tmp/%s' % filename

        kit = PDFKit.new(html, :page_size => 'Letter')
        #file = kit.to_file(file_path)

        content_type "application/octet-stream"
        header['Content-Disposition'] = "attachment; filename=%s" % filename
        env['api.format'] = :binary

        #body file.read
        body kit.to_pdf
      end
    end

  end
end