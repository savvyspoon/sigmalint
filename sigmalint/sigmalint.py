import click
import os
import io
import yaml
import pyrx
import jsonschema
import hiyapyco
import pprint

from .schema import rx_schema, json_schema, s2_schema

rx = pyrx.Factory({'register_core_types': True})

schema = rx.make_schema(rx_schema)

@click.command()
@click.option('--sigmainput', type=click.Path(exists=True, file_okay=True, readable=True, resolve_path=True), help='Path to a directory that comtains Sigma files or to a single Sigma file.', required=True)
@click.option('--directory', is_flag=True, help="Flag for if sigmainput is a directory")
@click.option('--method', type=click.Choice(['rx', 'jsonschema', 's2'], case_sensitive=False), default='rx', help='Validation method.')
def cli(sigmainput, directory, method):
    results = []
    filepaths = []
    
    if(directory):
        print("Directory True")
        filepaths = [os.path.join(dp, f) for dp, dn, fn in os.walk(os.path.expanduser(sigmainput)) for f in fn]
    else:
        seperator = '\\'
        filepaths=[sigmainput]
        pathParts = sigmainput.split(seperator)
        a_filename = pathParts[-1]
        pathParts.pop()
        sigmainput = seperator.join(pathParts)

    invalid_count = 0
    unsupported_count = 0

    with click.progressbar(filepaths, label="Parsing yaml files:") as bar:
        for filename in bar:
            if filename.endswith('.yml'):
                f = open(os.path.join(sigmainput, filename), 'r')
                sigma_yaml = yaml.safe_load_all(f)
                sigma_yaml_list = list(sigma_yaml)
                success_count = 0
                if len(sigma_yaml_list) > 1:
                    if method == 'rx':
                        #Set a limit for the total number of items
                        sigma_yaml_list_count = len(sigma_yaml_list)
                        
                        #Set a var for the first item in the list of yaml items
                        head = yaml.dump(sigma_yaml_list[0])
                        
                        #Use iter to skip the first item 
                        iteritems = iter(sigma_yaml_list)
                        next(iteritems)
                        
                        for item in iteritems:
                            section = yaml.dump(item)
                            combined =  hiyapyco.load(head, section, method=hiyapyco.METHOD_MERGE)
                            combined_yaml = hiyapyco.dump(combined, default_flow_style=False)
                            result = schema.check(combined_yaml)
                            if result:
                                success_count += 1
                        if(success_count == (sigma_yaml_list_count - 1)):
                            reason = 'valid' 
                        else:
                            reason = 'invalid'
                        results.append({'result': result, 'reasons': [reason], 'filename': filename})
                    elif method == 'jsonschema' or method == 's2':
                        method_schema = json_schema if method == 'jsonschema' else s2_schema
                        v = jsonschema.Draft7Validator(method_schema)
                        errors = []
                        for error in sorted(v.iter_errors(sigma_yaml_list[0]), key=str):    
                            errors.append(error.message)
                        result = False if len(errors) > 0 else True
                        results.append({'result': result, 'reasons': errors, 'filename': filename})
                else:
                    if method == 'rx':
                        result = schema.check(sigma_yaml_list[0])
                        reason = 'valid' if result else 'invalid'
                        results.append({'result': result, 'reasons': [reason], 'filename': filename})
                    elif method == 'jsonschema' or method == 's2':
                        method_schema = json_schema if method == 'jsonschema' else s2_schema
                        v = jsonschema.Draft7Validator(method_schema)
                        errors = []
                        for error in sorted(v.iter_errors(sigma_yaml_list[0]), key=str):    
                            errors.append(error.message)
                        result = False if len(errors) > 0 else True
                        results.append({'result': result, 'reasons': errors, 'filename': filename})

    click.echo('Results:')

    for result in results:
        color = 'green' if result['result'] else 'red'
        if result['reasons']:
            if 'Multi-document' in result['reasons'][0]:
                color = 'yellow'
        if result['result'] == False:
            invalid_count = invalid_count + 1
            click.echo('========')
            click.secho('{} is invalid:'.format(os.path.join(sigmainput, result['filename'])), fg=color)
            for reason in result['reasons']:
                click.secho('\t * ' + reason, fg=color)

    click.echo('Total Valid Rule Files: {}'.format(str(len(results) - invalid_count) + "/" + str(len(results))))
    click.echo('Total Invalid Rule Files: {}'.format(str(invalid_count) + "/" + str(len(results))))
    click.echo('Total Unsupported Rule Files (Multi-document): {}'.format(str(unsupported_count) + "/" + str(len(results))))