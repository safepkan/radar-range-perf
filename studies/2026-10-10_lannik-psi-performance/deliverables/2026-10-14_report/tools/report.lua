-- PDF rendering of the study's README.md: links into the repository lead
-- nowhere in a PDF, so they become plain text; figures fill the text width.
-- A link to a section of another file keeps the file's name, given once for
-- a run of such links into the same file: "(NOTES.md: “Loss terms”)".

local function is_web(link)
  return link.target:match('^https?://') ~= nil
end

local function section_file(inline)
  if inline.t == 'Link' and not is_web(inline) then
    return inline.target:match('^([^#]+)#.')
  end
end

local function continues_run(inline)
  return inline.t == 'Space' or inline.t == 'SoftBreak'
    or (inline.t == 'Str' and inline.text == ',')
end

-- Links are handled here rather than in a Link function, which Pandoc would
-- run first and so leave no links to group.
function Inlines(inlines)
  local result = pandoc.Inlines {}
  local run_file = nil
  for _, inline in ipairs(inlines) do
    local file = section_file(inline)
    if file then
      if file ~= run_file then
        result:extend { pandoc.Str(file .. ':'), pandoc.Space() }
      end
      result:insert(pandoc.Quoted('DoubleQuote', inline.content))
      run_file = file
    else
      if inline.t == 'Link' and not is_web(inline) then
        result:extend(inline.content)
      else
        result:insert(inline)
      end
      if not continues_run(inline) then
        run_file = nil
      end
    end
  end
  return result
end

function Image(image)
  image.attributes.width = '100%'
  return image
end

-- The italic paragraph under each figure is its caption; drop the one
-- Pandoc makes from the image's alt text.
function Figure(figure)
  return figure.content
end
