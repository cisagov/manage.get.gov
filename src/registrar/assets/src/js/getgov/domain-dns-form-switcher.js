class DNSFormSwitcher{
    /**
     * Manages DNS form switching from Alpine Data
     * Requires an HTML container with Alpine.js initialized on it
     * 
     * State:
     * - pending: an object { type, recordId} representing the form the user is currently on
     *   type is either "edit" or "add", recordID is the form's recordID
     * - target: the form  ID the user is clicking to.
     * 
     * Methods
     * - getAlpineData: returns the Alpine data object for the container
     * - resetPendingAndTarget: resets the target, and pending values to null
     *
    */ 
   
    constructor(container){
        this.pending = null;
        this.target = null;
        this.container = container;
    }

    setPending(value) {
         this.pending = value;
    }


    getAlpineData(){
        return Alpine.$data(this.container);
    }


    resetPendingAndTarget(){
       this.setTarget(null);
       this.setPending(null);
    }

}

export class EditFormSwitcher extends DNSFormSwitcher{
    /**
     * EditFormSwitcher for changes between edit forms, and opening the add record
     * State: inherited from DNSFormSwitcher
     * showFormId: the form number that is set on showFormId on Alpine data will show on the UI
     * Methods:
     * - setTarget: toggle from closing and opening the form if same value, and if different value set the form target;
     * - setShowFormId: update the showFormId in Alpine data
     * - getCurrentShowFormId: get current showFormId from Alpine data
     * - attemptOpen: sets the pending target in a dict to be used in the refsForm method to get the focusId, buttonId, and something else I forgot
     * - switchForm: uses setShowFormId to switch showFormId to current target, and reset the target and pending values
     */

    setTarget(value){  
        const current = this.getCurrentShowFormId();
        this.target = current == value ? null : value;
    }

    setShowId(value){
        const data = this.getAlpineData();
        data.showFormId = value;
    }
   
    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }

    getCurrentShowFormId(){
        return this.getAlpineData().showFormId
    }

    createReq(currentId){
      return {
            type: currentId > 0 ? "edit" : "add",
            recordId: currentId
        }
    }
   
    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getCurrentShowFormId();
         this.setPending(this.createReq(currentId));
    }

    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }
}

export class RecordSelectTypeSwitcher extends DNSFormSwitcher{

    constructor(container){
        super(container);
        this.isRecordType = true;
    }

    createReq(currentId){
       return {
            type: 'add',
            recordId: currentId,
            isRecordType: this.isRecordType
        }
    }

    setTarget(value){
        this.target = value;
    }

    setRecordType(value = this.target){
        const data = this.getAlpineData();
        data.recordType = this.target;
    }

    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getAlpineData().recordType;
        this.setPending(this.createReq(currentId));
    }

    updateSelectedType(value = this.target){
        this.container.selectedIndex = value;
    }

    switchForm(){
       this.setRecordType(this.target);
       this.updateSelectedType();
       this.resetPendingAndTarget();
    }
}