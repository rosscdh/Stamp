require 'grape'
require './lib/services'

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
        header "Cache-Control", "no-cache, max-age=0"

        html = params[:html]
        filename = params[:filename]

        service = Stamp::HTML2PDFService.new html, filename

        content_type "application/octet-stream"
        header['Content-Disposition'] = "attachment; filename=%s" % filename
        env['api.format'] = :binary

        body service.as_inline_pdf
      end
    end

  end
end